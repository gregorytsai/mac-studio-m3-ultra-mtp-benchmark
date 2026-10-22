import os
import sys
import time
import json
import signal
import subprocess
import urllib.request
import urllib.error
import statistics

# Public adaptation: supply your own local prompts and model config.
# Historical timing results are separate; synthetic prompts do not reproduce them.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_FILE = os.environ.get("BENCH_PROMPTS", os.path.join(BASE_DIR, "prompts.synthetic.json"))
MODELS_FILE = os.environ.get("BENCH_MODELS", os.path.join(BASE_DIR, "models_config.example.json"))
WORK_DIR = os.environ.get("BENCH_OUTPUT", os.path.join(BASE_DIR, "local_results"))
os.makedirs(WORK_DIR, exist_ok=True)
OUTPUT_DIR = os.path.join(WORK_DIR, "prompts_output")
RAW_RESULTS_FILE = os.path.join(WORK_DIR, "benchmark_results_raw.json")
SUMMARY_MD_FILE = os.path.join(WORK_DIR, "benchmark_summary.md")
SERVER_BIN = os.environ.get("LLAMA_SERVER", "llama-server")

PORT = 8088
NUM_RUNS = 5
MAX_TOKENS = 4096
TEMPERATURE = 0.7

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def wait_for_server(port, timeout=90):
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        return time.time() - start
        except Exception:
            pass
        time.sleep(0.3)
    return None

def query_chat(port, model_id, prompt_text, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, retries=3):
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=400) as resp:
                res = json.loads(resp.read().decode())
            t1 = time.time()
            wall_time = t1 - t0
            return res, wall_time
        except Exception as e:
            print(f"   ⚠️ query_chat failed (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise

def calc_stats(runs):
    gen_speeds = [r["gen_speed_tps"] for r in runs]
    wall_times = [r["wall_time_s"] for r in runs]
    completion_tokens = [r["completion_tokens"] for r in runs]
    acc_rates = [r["draft_acc_percent"] for r in runs if r.get("draft_n", 0) > 0]
    
    # Run 1: Cold start
    first_run = runs[0] if runs else {}
    cold_prefill_tps = first_run.get("prefill_speed_tps", 0.0)
    cold_prefill_ms = first_run.get("prefill_time_ms", 0.0)
    cold_cached_tokens = first_run.get("cached_tokens", 0)
    
    # Runs 2..5: Warm / KV-Cache hits
    warm_runs = runs[1:] if len(runs) > 1 else []
    cached_prefills = [r["prefill_time_ms"] for r in warm_runs if r.get("prefill_time_ms", 0) > 0]
    cached_tokens_list = [r["cached_tokens"] for r in warm_runs]
    
    mean_warm_prefill_ms = statistics.mean(cached_prefills) if cached_prefills else 0.0
    mean_cached_tokens = statistics.mean(cached_tokens_list) if cached_tokens_list else 0
    cache_speedup = (cold_prefill_ms / mean_warm_prefill_ms) if (cold_prefill_ms > 0 and mean_warm_prefill_ms > 0) else 1.0
    
    return {
        "cold_prefill_tps": cold_prefill_tps,
        "cold_prefill_ms": cold_prefill_ms,
        "cold_cached_tokens": cold_cached_tokens,
        "mean_warm_prefill_ms": mean_warm_prefill_ms,
        "mean_cached_tokens": mean_cached_tokens,
        "cache_speedup_x": cache_speedup,
        "mean_gen_speed_tps": statistics.mean(gen_speeds) if gen_speeds else 0.0,
        "std_gen_speed_tps": statistics.stdev(gen_speeds) if len(gen_speeds) > 1 else 0.0,
        "mean_wall_time_s": statistics.mean(wall_times) if wall_times else 0.0,
        "mean_completion_tokens": statistics.mean(completion_tokens) if completion_tokens else 0,
        "mean_acc_rate_percent": statistics.mean(acc_rates) if acc_rates else 0.0
    }

def get_model_variants(m):
    variants = [
        {
            "slug": "no_mtp",
            "name": "No MTP (Baseline)",
            "spec_type": "none",
            "draft_path": None,
            "draft_quant": "None",
            "draft_n": 0
        }
    ]
    for opt in m.get("mtp_options", []):
        opt_path = opt.get("path")
        if opt_path and os.path.exists(opt_path):
            opt_slug = opt.get("slug", "mtp")
            opt_label = opt.get("label", "MTP")
            opt_quant = opt.get("quant", "Draft")
            for n in [1, 2, 3, 4]:
                variants.append({
                    "slug": f"{opt_slug}_n{n}",
                    "name": f"{opt_label} (N={n})",
                    "spec_type": "draft-mtp",
                    "draft_path": opt_path,
                    "draft_quant": opt_quant,
                    "draft_n": n
                })
    return variants

def compute_group_aggregates(prompts_res, prompts_cfg):
    counseling_speeds = []
    counseling_colds = []
    counseling_cache_x = []
    counseling_accs = []
    counseling_walls = []
    
    agent_speeds = []
    agent_colds = []
    agent_cache_x = []
    agent_accs = []
    agent_walls = []
    
    all_speeds = []
    all_colds = []
    all_cache_x = []
    all_accs = []
    all_walls = []

    for p_id, p_info in prompts_cfg.items():
        if p_id not in prompts_res:
            continue
        st = prompts_res[p_id]["stats"]
        cat = p_info.get("category", "counseling")
        
        all_speeds.append(st["mean_gen_speed_tps"])
        if st["cold_prefill_tps"] > 0:
            all_colds.append(st["cold_prefill_tps"])
        all_cache_x.append(st["cache_speedup_x"])
        if st["mean_acc_rate_percent"] > 0:
            all_accs.append(st["mean_acc_rate_percent"])
        all_walls.append(st["mean_wall_time_s"])
        
        if cat == "counseling":
            counseling_speeds.append(st["mean_gen_speed_tps"])
            if st["cold_prefill_tps"] > 0:
                counseling_colds.append(st["cold_prefill_tps"])
            counseling_cache_x.append(st["cache_speedup_x"])
            if st["mean_acc_rate_percent"] > 0:
                counseling_accs.append(st["mean_acc_rate_percent"])
            counseling_walls.append(st["mean_wall_time_s"])
        elif cat == "agent":
            agent_speeds.append(st["mean_gen_speed_tps"])
            if st["cold_prefill_tps"] > 0:
                agent_colds.append(st["cold_prefill_tps"])
            agent_cache_x.append(st["cache_speedup_x"])
            if st["mean_acc_rate_percent"] > 0:
                agent_accs.append(st["mean_acc_rate_percent"])
            agent_walls.append(st["mean_wall_time_s"])

    def safe_mean(lst, default=0.0):
        return statistics.mean(lst) if lst else default

    return {
        "counseling": {
            "mean_gen_speed_tps": safe_mean(counseling_speeds),
            "mean_cold_prefill_tps": safe_mean(counseling_colds),
            "mean_cache_speedup_x": safe_mean(counseling_cache_x, 1.0),
            "mean_acc_rate_percent": safe_mean(counseling_accs),
            "mean_wall_time_s": safe_mean(counseling_walls)
        },
        "agent": {
            "mean_gen_speed_tps": safe_mean(agent_speeds),
            "mean_cold_prefill_tps": safe_mean(agent_colds),
            "mean_cache_speedup_x": safe_mean(agent_cache_x, 1.0),
            "mean_acc_rate_percent": safe_mean(agent_accs),
            "mean_wall_time_s": safe_mean(agent_walls)
        },
        "overall": {
            "mean_gen_speed_tps": safe_mean(all_speeds),
            "mean_cold_prefill_tps": safe_mean(all_colds),
            "mean_cache_speedup_x": safe_mean(all_cache_x, 1.0),
            "mean_acc_rate_percent": safe_mean(all_accs),
            "mean_wall_time_s": safe_mean(all_walls)
        }
    }

def update_markdown_summary(all_results, models_cfg, prompts_cfg):
    lines = []
    lines.append("# LLM Multi-Model Speculative Decoding (MTP), Cold-Start & KV-Cache Benchmark Report")
    lines.append(f"\n> **評測日期**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> **測試主機**: Runtime host: record separately for this run  ")
    lines.append("> **推論引擎**: llama.cpp (version must be recorded separately for this run)  ")
    lines.append(f"> **測試協定**: `max_tokens = {MAX_TOKENS}`, `temperature = {TEMPERATURE}`, 每個題目皆重複執行 `{NUM_RUNS}` 次  ")
    lines.append("> **統計分組**: 前 3 題為『**輔導工作文字處理**』、後 2 題為『**Agent工作**』，並計算各自與整體之平均分數。  ")
    lines.append("> **指標說明**: 包含**模型載入時間**、**冷啟動 Prefill（首次無快取）**、**KV 快取命中加速比（第2~5次）**、**自回歸生成速度** 與 **MTP 採納率**。  \n")
    
    lines.append("## 一、 測試題目說明 (Evaluation Prompts)")
    for p_id, p_info in prompts_cfg.items():
        cat_tag = f"【{p_info.get('category_name', '一般')}】"
        lines.append(f"- **{cat_tag} {p_info['title']} (`{p_id}`)**: {p_info['description']}")
    lines.append("\n---\n")
    
    lines.append("## 二、 綜合效能統計總表 (Performance Matrix)")
    lines.append("| 模型 (Model) | MTP 配置 | 載入時間 (s) | 題目 / 類別評估 | 生成速度 (Gen t/s) | 首次冷啟動 Prefill | 命中 KV 快取耗時 | 快取加速比 | Draft 採納率 (%) | 平均總耗時 (s) |")
    lines.append("| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for m in models_cfg:
        m_id = m["id"]
        if m_id not in all_results:
            continue
        m_data = all_results[m_id]
        m_name = m["display_name"]
        
        for v_slug, v_data in m_data.get("variants", {}).items():
            cfg_name = v_data["config_name"]
            load_t = f"{v_data.get('load_time_s', 0):.2f}s"
            prompts_res = v_data.get("prompts", {})
            
            # Print each individual prompt
            for p_id, p_info in prompts_cfg.items():
                if p_id not in prompts_res:
                    continue
                p_res = prompts_res[p_id]
                p_title = p_info["title"]
                st = p_res["stats"]
                
                gen_s = f"**{st['mean_gen_speed_tps']:.2f}** ± {st['std_gen_speed_tps']:.2f}"
                cold_s = f"**{st['cold_prefill_tps']:.1f} t/s** ({st['cold_prefill_ms']:.1f}ms)" if st['cold_prefill_tps'] > 0 else "N/A"
                warm_s = f"{st['mean_warm_prefill_ms']:.2f} ms" if st['mean_warm_prefill_ms'] > 0 else "N/A"
                cache_x = f"**{st['cache_speedup_x']:.1f}x**" if st['cache_speedup_x'] > 1.0 else "1.0x"
                acc_s = f"{st['mean_acc_rate_percent']:.1f}%" if st['mean_acc_rate_percent'] > 0 else "N/A"
                wall_s = f"{st['mean_wall_time_s']:.2f}s"
                
                lines.append(f"| {m_name} | {cfg_name} | {load_t} | {p_title} | {gen_s} | {cold_s} | {warm_s} | {cache_x} | {acc_s} | {wall_s} |")
                
            # If all prompts completed, append category subtotal averages
            if len(prompts_res) == len(prompts_cfg):
                agg = compute_group_aggregates(prompts_res, prompts_cfg)
                c_agg = agg["counseling"]
                a_agg = agg["agent"]
                o_agg = agg["overall"]
                
                lines.append(f"| {m_name} | {cfg_name} | {load_t} | 📝 **[分組平均] 輔導工作文字處理 (前3題)** | **{c_agg['mean_gen_speed_tps']:.2f}** | **{c_agg['mean_cold_prefill_tps']:.1f} t/s** | - | **{c_agg['mean_cache_speedup_x']:.1f}x** | {c_agg['mean_acc_rate_percent']:.1f}% | {c_agg['mean_wall_time_s']:.2f}s |")
                lines.append(f"| {m_name} | {cfg_name} | {load_t} | 🤖 **[分組平均] Agent工作 (後2題)** | **{a_agg['mean_gen_speed_tps']:.2f}** | **{a_agg['mean_cold_prefill_tps']:.1f} t/s** | - | **{a_agg['mean_cache_speedup_x']:.1f}x** | {a_agg['mean_acc_rate_percent']:.1f}% | {a_agg['mean_wall_time_s']:.2f}s |")
                lines.append(f"| {m_name} | {cfg_name} | {load_t} | ⭐ **[全題總平均] 全題綜合評估 (全5題)** | **{o_agg['mean_gen_speed_tps']:.2f}** | **{o_agg['mean_cold_prefill_tps']:.1f} t/s** | - | **{o_agg['mean_cache_speedup_x']:.1f}x** | {o_agg['mean_acc_rate_percent']:.1f}% | {o_agg['mean_wall_time_s']:.2f}s |")
                lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
                
    lines.append("\n---\n")
    lines.append("## 三、 模型 MTP 梯度、分組表現與效益總結 (Model Scaling Analysis)")
    for m in models_cfg:
        m_id = m["id"]
        if m_id not in all_results:
            continue
        m_data = all_results[m_id]
        lines.append(f"### {m['display_name']}")
        lines.append(f"- **模型檔案**: `{m['model_path']}`")
        mtp_list = [f"{opt.get('label')} ({opt.get('quant')} - `{opt.get('path')}`)" for opt in m.get("mtp_options", [])]
        lines.append(f"- **可用 MTP 模型**: {', '.join(mtp_list) if mtp_list else '無 (Native MoE / Baseline)'}")
        lines.append("\n| MTP 配置 | 載入時間 | 全題總平均 (t/s) | 輔導工作平均 (t/s) | Agent工作平均 (t/s) | MTP 採納率 | 快取加速比 | 相對 Baseline 加速 |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        
        base_speed = None
        for v_slug, v_data in m_data.get("variants", {}).items():
            cfg_name = v_data["config_name"]
            load_t = f"{v_data.get('load_time_s', 0):.2f}s"
            prompts_res = v_data.get("prompts", {})
            if not prompts_res:
                continue
                
            agg = compute_group_aggregates(prompts_res, prompts_cfg)
            avg_speed = agg["overall"]["mean_gen_speed_tps"]
            c_speed = agg["counseling"]["mean_gen_speed_tps"]
            a_speed = agg["agent"]["mean_gen_speed_tps"]
            avg_acc = agg["overall"]["mean_acc_rate_percent"]
            avg_cache_x = agg["overall"]["mean_cache_speedup_x"]
            
            if base_speed is None or v_slug == "no_mtp":
                base_speed = avg_speed
                speedup_str = "基準 (1.00x)"
            else:
                pct = ((avg_speed - base_speed) / base_speed * 100) if base_speed > 0 else 0
                speedup_str = f"**+{pct:.1f}%**"
                
            acc_str = f"{avg_acc:.1f}%" if avg_acc > 0 else "N/A"
            cache_str = f"**{avg_cache_x:.1f}x**"
            lines.append(f"| {cfg_name} | {load_t} | **{avg_speed:.2f} t/s** | **{c_speed:.2f} t/s** | **{a_speed:.2f} t/s** | {acc_str} | {cache_str} | {speedup_str} |")
        lines.append("\n")
        
    with open(SUMMARY_MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def run_suite(target_model=None):
    prompts_cfg = load_json(PROMPTS_FILE)
    models_cfg = load_json(MODELS_FILE)["models"]
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_results = {}
    if os.path.exists(RAW_RESULTS_FILE):
        try:
            all_results = load_json(RAW_RESULTS_FILE)
        except Exception:
            all_results = {}
            
    print("=" * 80)
    print("🚀 Starting Complete Multi-Model Multi-MTP Benchmark Suite")
    print("   Metrics: Model Load Time, Cold Prefill, Warm KV Cache, Gen Speed, MTP Acc")
    print("   Categories: [1] 輔導工作文字處理 (Prompts 1-3) | [2] Agent工作 (Prompts 4-5)")
    print(f"   Models: {len(models_cfg)} | Prompts: {len(prompts_cfg)} | Runs per prompt: {NUM_RUNS}")
    if target_model:
        print(f"   🎯 Targeted Execution: ONLY running model '{target_model}'")
    print("=" * 80)
    
    for m in models_cfg:
        m_id = m["id"]
        if target_model and m_id != target_model:
            continue
        m_name = m["display_name"]
        variants = get_model_variants(m)
        
        if m_id not in all_results:
            all_results[m_id] = {
                "id": m_id,
                "display_name": m_name,
                "model_path": m["model_path"],
                "variants": {}
            }
            
        print(f"\n=================================================================")
        print(f"📦 [Model] {m_name}")
        print(f"   Model: {m['model_path']}")
        print(f"   Total Variants ({len(variants)}): {[v['name'] for v in variants]}")
        print(f"=================================================================")
        
        for v in variants:
            v_slug = v["slug"]
            v_name = v["name"]
            
            if v_slug in all_results[m_id]["variants"]:
                if len(all_results[m_id]["variants"][v_slug].get("prompts", {})) == len(prompts_cfg):
                    print(f"⏩ [Skip] {m_name} -> {v_name} already completed. Resuming...")
                    continue
                    
            print(f"\n--- [Variant] {m_name} | {v_name} ---")
            
            cmd = [
                SERVER_BIN,
                "--model", m["model_path"],
                "--host", "127.0.0.1",
                "--port", str(PORT),
                "--jinja",
                "--flash-attn", "on",
                "--n-gpu-layers", "all",
                "-c", str(m.get("ctx_size", 16384)),
                "-b", "2048",
                "-ub", "2048",
                "--alias", m_id,
                "--log-verbosity", "2"
            ]
            
            if m.get("mmproj_path") and os.path.exists(m["mmproj_path"]):
                cmd.extend(["--mmproj", m["mmproj_path"]])
                
            if v["spec_type"] == "none" or not v.get("draft_path"):
                cmd.extend(["--spec-type", "none"])
            else:
                cmd.extend([
                    "--model-draft", v["draft_path"],
                    "--spec-type", v["spec_type"],
                    "--spec-draft-n-max", str(v["draft_n"])
                ])
                
            log_file = f"/tmp/bench_{m_id}_{v_slug}.log"
            with open(log_file, "w") as lf:
                proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
                
            print(f"⏳ Starting server (PID {proc.pid}). Measuring model load time...")
            load_time_s = wait_for_server(PORT, timeout=90)
            if load_time_s is None:
                print(f"❌ Failed to start server for {m_name} ({v_name})")
                proc.kill()
                continue
            print(f"✅ Model loaded and server online in {load_time_s:.2f} seconds!")
            
            if v_slug in all_results[m_id]["variants"]:
                v_result = all_results[m_id]["variants"][v_slug]
            else:
                v_result = {
                    "config_name": v_name,
                    "spec_type": v["spec_type"],
                    "draft_path": v.get("draft_path"),
                    "draft_quant": v.get("draft_quant"),
                    "draft_n": v["draft_n"],
                    "load_time_s": load_time_s,
                    "prompts": {}
                }
            
            try:
                for p_id, p_info in prompts_cfg.items():
                    p_title = p_info["title"]
                    p_content = p_info["content"]
                    cat_name = p_info.get("category_name", "一般")
                    
                    if p_id in v_result.get("prompts", {}):
                        print(f"  ⏩ [Skip Prompt] {p_title} ({p_id}) already completed. Resuming...")
                        continue
                        
                    print(f"  👉 Prompt: [{cat_name}] {p_title} ({p_id}) x {NUM_RUNS} runs...")
                    p_runs = []
                    for i in range(1, NUM_RUNS + 1):
                        p_max_tok = p_info.get("max_tokens", MAX_TOKENS)
                        res, wall_t = query_chat(PORT, m_id, p_content, max_tokens=p_max_tok)
                        timings = res.get("timings", {})
                        usage = res.get("usage", {})
                        
                        gen_tps = timings.get("predicted_per_second", usage.get("completion_tokens", 0) / wall_t if wall_t > 0 else 0)
                        pref_tps = timings.get("prompt_per_second", 0)
                        pref_ms = timings.get("prompt_ms", 0)
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                        
                        draft_n = timings.get("draft_n", 0)
                        draft_acc = timings.get("draft_n_accepted", 0)
                        acc_rate = (draft_acc / draft_n * 100) if draft_n > 0 else 0.0
                        
                        run_entry = {
                            "iteration": i,
                            "wall_time_s": wall_t,
                            "prompt_tokens": prompt_tokens,
                            "cached_tokens": cached_tokens,
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "prefill_speed_tps": pref_tps,
                            "prefill_time_ms": pref_ms,
                            "gen_speed_tps": gen_tps,
                            "gen_time_ms": timings.get("predicted_ms", 0),
                            "draft_n": draft_n,
                            "draft_n_accepted": draft_acc,
                            "draft_acc_percent": acc_rate
                        }
                        p_runs.append(run_entry)
                        
                        cache_status = f"FIRST ({cached_tokens}/{prompt_tokens} cached)" if i == 1 else f"🔥 WARM ({cached_tokens}/{prompt_tokens} cached)"
                        print(f"     [Run {i}/{NUM_RUNS}] {cache_status} | Gen: {gen_tps:.2f} t/s | Prefill: {pref_ms:.1f}ms ({pref_tps:.1f} t/s) | Acc: {acc_rate:.1f}% | Wall: {wall_t:.2f}s")
                        
                        if i == 1:
                            out_path = os.path.join(OUTPUT_DIR, f"{m_id}_{v_slug}_{p_id}.txt")
                            msg = res.get("choices", [{}])[0].get("message", {})
                            with open(out_path, "w", encoding="utf-8") as out_f:
                                out_f.write(f"=== Model: {m_name} | Config: {v_name} | Load Time: {load_time_s:.2f}s ===\n")
                                out_f.write(f"=== Prompt: {p_title} (Category: {cat_name}) ===\n\n")
                                if msg.get("reasoning_content"):
                                    out_f.write("--- REASONING CONTENT ---\n")
                                    out_f.write(msg["reasoning_content"] + "\n\n")
                                out_f.write("--- FINAL CONTENT ---\n")
                                out_f.write(msg.get("content", "") + "\n")
                                
                    p_stats = calc_stats(p_runs)
                    v_result["prompts"][p_id] = {
                        "title": p_title,
                        "category": p_info.get("category", "counseling"),
                        "category_name": cat_name,
                        "stats": p_stats,
                        "runs": p_runs
                    }
                    print(f"     >> Avg Gen Speed: {p_stats['mean_gen_speed_tps']:.2f} ± {p_stats['std_gen_speed_tps']:.2f} t/s | Cold Prefill: {p_stats['cold_prefill_tps']:.1f} t/s | Cache Speedup: {p_stats['cache_speedup_x']:.1f}x | Acc: {p_stats['mean_acc_rate_percent']:.1f}%")
                    
                    all_results[m_id]["variants"][v_slug] = v_result
                    with open(RAW_RESULTS_FILE, "w", encoding="utf-8") as rf:
                        json.dump(all_results, rf, ensure_ascii=False, indent=2)
                    update_markdown_summary(all_results, models_cfg, prompts_cfg)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

            
    print("\n" + "=" * 80)
    print("🎉 FULL BENCHMARK MATRIX COMPLETED SUCCESSFULLY!")
    print(f"Raw results saved to: {RAW_RESULTS_FILE}")
    print(f"Markdown report saved to: {SUMMARY_MD_FILE}")
    print("=" * 80)

if __name__ == "__main__":
    target = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        target = sys.argv[1]
    elif "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    run_suite(target_model=target)
