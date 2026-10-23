"""Build the public static site from sanitized metrics. Standard library only."""
import json, math, statistics as st, html, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=json.loads((ROOT/'data/analysis.json').read_text(encoding='utf-8'))
RAW=json.loads((ROOT/'data/benchmark_metrics.json').read_text(encoding='utf-8'))
META=json.loads((ROOT/'data/model_sources.json').read_text(encoding='utf-8'))
E=html.escape
repo='https://github.com/gregorytsai/mac-studio-m3-ultra-mtp-benchmark'
SITE='https://gregorytsai.github.io/mac-studio-m3-ultra-mtp-benchmark/'
pct=lambda x:f'{(x-1)*100:+.1f}%'
def table(headers,rows):
 return '<div class="table-wrap"><table><thead><tr>'+''.join(f'<th>{E(str(h))}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def chart(series,title,max_y=80):
 colors=['#176bab','#b9511c']; parts=[f'<svg class="chart" viewBox="0 0 640 350" role="img" aria-label="{E(title)}"><title>{E(title)}</title>']
 for val in range(0,max_y+1,20):
  y=280-val/max_y*220
  parts.append(f'<line x1="60" y1="{y}" x2="600" y2="{y}" stroke="#d9e2e7"/><text x="49" y="{y+5}" text-anchor="end" fill="#506678" font-size="13">{val}%</text>')
 for i in range(4):parts.append(f'<text x="{95+i*155}" y="315" text-anchor="middle" fill="#506678" font-size="15">N = {i+1}</text>')
 for j,(label,values) in enumerate(series):
  pts=[(95+i*155,280-v/max_y*220) for i,v in enumerate(values)]
  parts.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{colors[j]}" stroke-width="3"/>')
  for i,((x,y),v) in enumerate(zip(pts,values)):
   other=series[1-j][1][i] if len(series)==2 else -math.inf
   offset=-14 if v>=other else 24
   parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{colors[j]}"/><text x="{x}" y="{y+offset}" text-anchor="middle" fill="{colors[j]}" font-size="16" font-weight="700">+{v:.1f}%</text>')
 parts.append('</svg><div class="legend">'+''.join(f'<span>{E(s[0])}</span>' for s in series)+'</div>')
 return ''.join(parts)
def page(file,title,body,extra=''):
 canonical=SITE+('' if file=='index.html' else file)
 nav=''.join(f'<a href="{p}"'+(' aria-current="page"' if file==p else '')+f'>{t}</a>' for p,t in [('index.html','設定指南'),('analysis.html','技術與分析'),('resources.html','資料與程式碼')])
 text=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="google-site-verification" content="mWQ59Rie_MkAK8-ilMG1MrZ9TO_OLtLBGmgvyCpdYcQ"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(title)}｜Mac Studio MTP 實測</title><meta name="description" content="Mac Studio M3 Ultra 256GB · 80 核心 GPU MTP 實測：用圖表比較六個模型與 N=1–4，找出適合文字與 Agent 題目的設定。"><link rel="canonical" href="{canonical}"><link rel="sitemap" type="application/xml" href="sitemap.xml"><link rel="stylesheet" href="assets/style.css"></head><body><a class="skip" href="#main">跳到主要內容</a><header><nav aria-label="主要導覽"><a class="brand" href="index.html">MTP / FIELD NOTES</a><div class="links">{nav}<a href="{repo}">GitHub ↗</a></div></nav></header><main id="main">{body}</main><footer>Mac Studio M3 Ultra · 256GB · 80 核心 GPU · 單機效能紀錄<br>共同作者：gregorytsai · OpenAI Codex · Gemini 3.8 Flash<br>分析整理：2026-10-22。速度結果不代表內容品質；以自己的工作負載驗證設定。<br>聯絡信箱：<a href="mailto:gregorytsai@gmail.com">gregorytsai@gmail.com</a> · <a href="sitemap.xml">網站地圖</a></footer>{extra}</body></html>'''
 for asset in ['style.css','chart-data.js','explore.js']:
  asset_path=ROOT/'assets'/asset
  if asset_path.exists():
   digest=hashlib.sha256(asset_path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()[:10]
   text=text.replace('assets/'+asset+'"','assets/'+asset+'?v='+digest+'"')
 (ROOT/file).write_text(text,encoding='utf-8')

effects=R['n_effects']
task_chart=chart([('輔導文字題',[(r['counseling']-1)*100 for r in effects]),('Agent 題',[(r['agent']-1)*100 for r in effects])],'N 對兩種任務的速度提升：輔導題 N2 最快，Agent 題 N4 最快')
cards=''
quants=[m['main_quant'] for m in META.values()]
for i,m in enumerate(R['by_model']):
 b=[b for b in R['best'] if b['model']==m['model']]
 cards+=f'<article class="model-card"><h3>{E(m["model"])}</h3><p class="model-spec">{quants[i]} · {"MoE" if i in [2,5] else "非 MoE"}</p>'
 for row in b:
  q,n=row['best_joint'].split('_')[1:];name='輔導文字' if row['category']=='counseling' else 'Agent 題'
  model_data=list(RAW.values())[i]
  selected=[p for p,z in model_data['variants']['no_mtp']['prompts'].items() if z['category']==row['category']]
  speed=st.mean(st.mean(r['gen_speed_tps'] for r in model_data['variants'][row['best_joint']]['prompts'][p]['runs']) for p in selected)
  baseline=st.mean(st.mean(r['gen_speed_tps'] for r in model_data['variants']['no_mtp']['prompts'][p]['runs']) for p in selected)
  cards+=f'<div class="task-result" data-card-task="{row["category"]}"><p class="card-task-name">{name}</p><div class="setting"><span>建議先試</span><b>{q.upper()} · N={n[1:]}</b></div><div class="speed-line"><strong>{speed:.1f}<small> tok/s</small></strong><span class="gain-badge" aria-label="生成速度提升 {(row["joint_gain"]-1)*100:.1f}%">↑ {(row["joint_gain"]-1)*100:.1f}%</span></div><p class="baseline">未開 MTP：{baseline:.1f} tok/s</p></div>'
 cards+='</article>'
# Same-Q, same-N comparisons isolate the displayed task contrast from configuration choice.
def task_gain(model_index,category,n):
 model=list(RAW.values())[model_index]
 ratios=[]
 for prompt,base in model['variants']['no_mtp']['prompts'].items():
  if base['category']!=category:continue
  speed=st.mean(r['gen_speed_tps'] for r in model['variants'][f'mtp_q4_n{n}']['prompts'][prompt]['runs'])
  baseline=st.mean(r['gen_speed_tps'] for r in base['runs'])
  ratios.append(speed/baseline)
 return math.exp(st.mean(math.log(x) for x in ratios))
spotlight=''
for i in [0,1]:
 series=[('諮商輔導文字',[(task_gain(i,'counseling',n)-1)*100 for n in range(1,5)]),('助理程式題',[(task_gain(i,'agent',n)-1)*100 for n in range(1,5)])]
 spotlight+=f'<article class="panel"><h3>{E(R["by_model"][i]["model"])}</h3><p class="small">主模型 UD-Q4_K_XL · 草稿固定 Q4</p>'+chart(series,'同一模型與草稿量化下，兩類任務隨 N 改變的速度提升',max_y=100)+f'<p class="spotlight-result">同樣 N=4：<b>輔導 {pct(task_gain(i,"counseling",4))}</b> ／ <b>程式 {pct(task_gain(i,"agent",4))}</b></p></article>'
research_intro='<p>公開實測已指出工作負載會影響 MTP 收益。這次補上的，是同一台 Mac Studio 上，諮商輔導文字與助理程式題的六模型對照，以及草稿 Q、N 的設定差異。</p>'
model_options=''.join(f'<option value="{i}">{E(x["model"])} · {quants[i]}</option>' for i,x in enumerate(R['by_model']))
body=f'''<div class="hero"><div><div class="eyebrow">Local LLM / Practical benchmark</div><h1>Mac Studio M3 Ultra 256GB · 80 核心 GPU<br>MTP 實測與設定指南</h1><p class="lead">同一個模型，換一種工作，MTP 的加速幅度與適合的 N 就可能不同。這次把諮商輔導文字與助理程式題放在同一台 Mac 上比較，讓設定更貼近你的實際工作。</p><div class="tags"><span class="tag">6 個模型</span><span class="tag">5 道題目</span><span class="tag">1,250 次執行</span><span class="tag">llama.cpp / Metal</span></div><a class="button" href="#task-findings">先看任務差異的發現 ↓</a> <a class="hero-link" href="#choose">直接查看模型設定 →</a></div><aside class="hero-figure"><h3>同模型、同題目比較</h3><div class="big">+40.7<span style="font-size:30px">%</span></div><p>開啟 MTP 後的平均生成速度提升</p><div class="meter"><span>不開 MTP</span><i style="width:50%"></i><strong>1.00×</strong></div><div class="meter accent"><span>開啟 MTP</span><i style="width:70.35%"></i><strong>1.41×</strong></div><p>六模型共同的草稿 Q4 條件，N=1–4 等權重。<br>這是輸出速度，不是回答品質分數。</p></aside></div>
<div class="keyline"><div><strong>先選工作，再選 N</strong><span class="small">依任務分別調整，比照抄單一 N 更值得測。</span></div><div><strong>Q8 不一定比較快</strong><span class="small">五模型平均比 Q4 慢約 1.3%。</span></div><div><strong>MoE 先試較低 N</strong><span class="small">本次兩個 MoE 模型以 N=1–2 較佳。</span></div></div>
<section><div class="section-head"><div><div class="eyebrow">01 / 先看懂設定</div><h2>MTP 是幫模型先打草稿</h2></div><p>主模型會檢查草稿，接受合適的部分。草稿猜得準，就可能一次前進更多；猜得不準，檢查與重算也會花時間。</p></div><div class="three"><div class="panel"><div class="step">MTP · 要不要先打草稿</div><h3>開啟後，多一道預測流程</h3><p>能否省時間，取決於預測帶來的收益是否超過額外成本。</p></div><div class="panel"><div class="step">N · 每次最多猜幾個 token</div><h3>從 1 到 4，逐步比較</h3><p>N 是本次設定的草稿長度上限，不是保證一次接受的數量。token 也不等於中文字數。</p></div><div class="panel"><div class="step">Q · 草稿模型的量化</div><h3>比較 Q4 與 Q8</h3><p>這裡的 Q 指草稿模型。Q8 通常需要更多記憶體，但不保證更快；主模型量化另有固定設定。</p></div></div></section>
<section><div class="section-head"><div><div class="eyebrow">02 / 讀圖找方向</div><h2>文字工作先試 N=2，<br>Agent 題可以再往上試</h2></div><p>圖越高，代表相對不開 MTP 的速度提升越多。藍線在 N=2 達到最高，橘線則持續上升。各模型仍有差異，下一區可逐一查看。</p></div><div class="panel">{task_chart}<p class="caption">草稿固定 Q4；主模型：Gemma 4 QAT 為 UD-Q4_K_XL、Qwen 3.8 27B 為 UD-Q8_K_XL、Flash Next 為 UD-Q6_K_XL。六模型等權重；輔導 3 題、Agent 2 題。Agent 題為程式生成與終端模擬，不是完整自主 Agent 的成功率測試。</p><details><summary>查看圖表數值</summary>{table(['N','輔導文字題','Agent 題'],[[r['n'],pct(r['counseling']),pct(r['agent'])] for r in effects])}</details></div></section>
<section id="task-findings"><div class="section-head"><div><div class="eyebrow">本次亮點 / 同一模型，兩種工作</div><h2>小模型也值得<br>依工作內容調整 N</h2></div><p>藍線是諮商輔導文字，橘線是助理程式題。兩張圖都固定草稿 Q4、使用相同刻度；往右增加 N，兩類任務的收益逐漸分開。</p></div><div class="two">{spotlight}</div><div class="callout"><strong>實測觀察：多猜幾個 token，不是每種工作都划算。</strong><p>在 E4B，輔導題 N=2 較快，程式題則以 N=4 較快；12B 的輔導題在 N=3 達到最高，程式題仍以 N=4 較快。若只測程式題就把 N=4 套到所有工作，可能錯過更適合文字工作的設定。</p></div><div class="hypothesis"><span class="tag">值得驗證的假設</span><h3>較小模型，可能特別值得採用「依任務選 N」</h3><p>E4B、12B 的兩條曲線分開得很清楚，因此值得測試：替不同工作保留各自的 N，是否比全服務固定一個 N 更實用？31B 也有明顯任務差異，所以這裡提出的是部署假設，還不是「越小差異越大」的規律。</p><p class="small">本次只有 3 道輔導文字題與 2 道助理程式題（程式生成、終端模擬）。這些是速度觀察，不代表完整 Agent 的成功率，也沒有評分諮商內容品質。</p></div><details><summary>為什麼可能出現這種差異？</summary><p>一個合理解釋是，程式中的固定格式、重複名稱與括號較容易被草稿猜中，較長的草稿因而可能更划算；文字工作則有不同的表達選擇。但題目長度、採樣、量化與引擎成本也會影響結果，本測試尚未把它們分開驗證。<a href="https://registry.ollama.com/blog/faster-gemma-4-mlx-mtp">Ollama 的 MTP 實測與機制說明</a>也提出程式可預測性與動態草稿長度的關係。</p></details><p><a href="analysis.html#related-work">與公開實測對照：這次補上哪些觀察 →</a></p></section>
<section id="choose"><div class="section-head"><div><div class="eyebrow">03 / 找到你的設定</div><h2>選模型，看看哪個 N 最適合先試</h2></div><p>比較的是同模型的相對加速。不同模型的 50% 提升，不代表實際 tok/s 相同。</p></div><div class="panel"><div class="controls"><div><label for="model">模型</label><select id="model">{model_options}</select></div><div><label for="task">工作類型</label><select id="task"><option value="counseling">輔導文字工作</option><option value="agent">Agent 題</option></select></div></div><div id="recommend" class="recommend" aria-live="polite"></div><div id="model-chart"></div><div id="model-table"></div><noscript><p>互動圖表需要 JavaScript。下方的設定速查表仍可直接閱讀。</p></noscript></div><p class="caption">最佳值由這批資料選出，尚未在新題目驗證。差距很小時，可優先試較低 N，再測自己的內容。</p></section>
<section id="quick-reference"><div class="eyebrow">04 / 設定速查</div><h2>六個模型的起始參考</h2><p class="reference-intro">依本次測試，挑選適合先試的設定；實際效果仍會隨題目改變。</p><div class="task-switch" role="group" aria-label="速查卡片的工作類型" hidden><button type="button" data-card-choice="counseling" aria-pressed="true">輔導文字</button><button type="button" data-card-choice="agent" aria-pressed="false">Agent 工作</button></div><p id="card-task-status" class="small" aria-live="polite">比較各模型的草稿 Q 與 N，顯示本次最快的組合。</p><div class="three reference-grid">{cards}</div><details class="calculation-details"><summary>數值怎麼算？</summary><p>卡片同時比較可用的草稿 Q 與 N；Qwen 3.8 27B 只有 Q4 資料。顯示的是本次最快觀察值，不是所有情境的固定答案。</p><p>tok/s 為任務內各題的平均生成速度，不含輸入處理（prefill）；提升百分比則先在同題內比較後取幾何平均，因此不一定等於卡片上兩個速度直接相除。Agent 工作使用程式生成與終端模擬題，並非完整自主 Agent 的成功率測試。</p></details><div class="note">Gemma 4 31B QAT 的輔導題：Q4 N=4 只比 N=3 快約 0.5%，兩者都值得試。若不想先逐一微調，可從 Q4 N=2 開始，再用自己的題目比較 N=3、4；E4B 則值得另外試 Q8。</div></section>
<section id="test-your-domain"><div class="section-head"><div><div class="eyebrow">給架設者 / 把自己的素材帶進來</div><h2>最值得測的題目，<br>是你每天真的會用的題目</h2></div><p>網路上的最佳 N 是起點。部署前，請準備自己領域的代表素材，在實際機器與服務設定下比較。</p></div><div class="three"><article class="panel"><div class="step">01 / 準備領域題組</div><h3>涵蓋不同內容與長度</h3><p>例如輔導文字的摘要、改寫、資訊整理，以及助理工作的程式修改、結構化輸出與工具指令。先用去識別或合成素材；保留專業術語、輸入長度及輸出格式。</p></article><article class="panel"><div class="step">02 / 同題比較設定</div><h3>從關閉 MTP 到 N=1–4</h3><p>固定模型、量化、採樣與輸出預算；每題重跑數次，打散設定順序，分開觀察冷啟動、快取與實際並行負載。用一部分題目選設定，再用未參與挑選的題目確認。</p></article><article class="panel"><div class="step">03 / 同時看速度與可用性</div><h3>快，還要真的完成工作</h3><p>記錄 tok/s、首字等待、總耗時與輸出量；另外檢查內容品質、格式是否正確、工具是否成功。MTP 接受率是草稿通過率，不是答案正確率。</p></article></div><p class="caption">現有公開 runner 保留原始固定順序；隨機順序、首字等待與品質評分需在下一輪另行加入，不能視為現有程式已具備。</p><a href="analysis.html#next-tests">查看值得共同驗證的五個方向 →</a></section>
<section class="two"><div class="panel"><div class="eyebrow">如何套用</div><h2>把 N 設在草稿長度上限</h2><p>在本次 llama.cpp 介面中，MTP 的關鍵參數如下。請換成與主模型相配的草稿檔案，並確認你的版本支援這些選項。</p><pre><code>--model-draft /path/to/draft.gguf
--spec-type draft-mtp
--spec-draft-n-max 2</code></pre><p class="small">將最後的 2 換成要測試的 N。其他執行參數與模型設定見技術頁。</p><a href="analysis.html#environment">查看完整測試條件 →</a></div><div class="panel"><div class="eyebrow">如何判斷</div><h2>在自己的工作上確認三件事</h2><ol><li>固定模型與題目，比較不開 MTP、N=2，再視結果增加 N。</li><li>看生成速度，也看總等待時間；輸出變長時，速度更快仍可能等更久。</li><li>檢查內容是否符合需求。這份測試沒有評分回答品質，不能替你判斷內容可用性。</li></ol><a href="resources.html">下載程式與公開數值 →</a></div></section>'''

gm=lambda x:math.exp(st.mean(math.log(v) for v in x))
plot=[]
for idx,(mid,model) in enumerate(RAW.items()):
 for cat in ['counseling','agent']:
  ps=[p for p,z in model['variants']['no_mtp']['prompts'].items() if z['category']==cat]
  options=[]
  for v,z in model['variants'].items():
   if v=='no_mtp':continue
   ratios=[];speeds=[]
   for p in ps:
    speed=st.mean(r['gen_speed_tps'] for r in z['prompts'][p]['runs']);base=st.mean(r['gen_speed_tps'] for r in model['variants']['no_mtp']['prompts'][p]['runs'])
    ratios.append(speed/base);speeds.append(speed)
   options.append({'q':v.split('_')[1].upper(),'n':int(v[-1]),'gain':gm(ratios),'tps':st.mean(speeds)})
  plot.append({'model':idx,'label':R['by_model'][idx]['model'],'quant':META[mid]['main_quant'],'category':cat,'options':options})
(ROOT/'assets/chart-data.js').write_text('window.BENCHMARK = '+json.dumps(plot,ensure_ascii=False)+';',encoding='utf-8')
page('index.html','Mac Studio M3 Ultra 256GB · 80 核心 GPU｜MTP 實測與設定指南',body,'<script src="assets/chart-data.js"></script><script src="assets/explore.js"></script>')

body='''<div class="page-title"><div class="eyebrow">Methods / Evidence / Limits</div><h1>技術與分析</h1><p class="lead">把「這批資料顯示什麼」與「還不能推論什麼」分開，讓設定建議有可追溯的依據。</p></div><div class="prose"><section id="environment"><h2>測試環境與資料來源</h2><p>NAS 環境紀錄：Mac Studio、Apple M3 Ultra，32 核心 CPU（24 效能＋8 節能），256GB 統一記憶體；Darwin 25.6.0 arm64。80 核心 GPU 由專案發起人補充確認。</p><p>推論環境記載 llama.cpp v0.7.0、commit 620d2225c、Metal、f16 KV cache 與 Metal peer memory。這些是原環境檔的紀錄，未在本次整理時重新登入測試機驗證。</p><pre><code>--host 127.0.0.1 --port 8088
--jinja --flash-attn on --n-gpu-layers all
-c 16384 -b 2048 -ub 2048
temperature = 0.7
max_tokens = 4096
runs per prompt = 5</code></pre><p>6 模型 × 各自可用設定 × 5 題，共 250 個條件、1,250 次執行。五模型有 baseline＋Q4/Q8×N1–4；Qwen 3.8 27B 只有 baseline＋Q4×N1–4。各設定的 context window 都是 16,384，沒有操弄 window 大小。輸入長度則隨題目與 tokenizer 不同。</p><div class="note"><strong>來源不一致的處理：</strong>舊 README 說 Flash Next 只測 baseline，但 JSON 有 Q4/Q8、N1–4 且接受率非零，故依實際數值記錄分析。舊報表程式的版本字樣是 v0.6.0，環境檔寫 v0.7.0，runner 也有版本回退邏輯；無完整執行 log，不能保證每次執行的二進位版本相同。E4B Q4 與 Q8 都標為 94MB，實際 GGUF 型別及檔案大小尚未驗證。</div></section>
<section><h2>數值如何計算</h2><ol><li>每個模型×設定×題目，先算 5 次生成速度的算術平均。</li><li>在同模型、同題目內，除以不開 MTP 的速度，得到加速比。</li><li>對加速比取幾何平均；模型等權重，兩類任務各佔 50%，類內題目等權重。</li></ol><p>共同設計使用 Q4。Q8/Q4 比較只用五個條件完整的模型，於同題目、同 N 配對。baseline 不具有 Q，不複製成兩份當作獨立觀察。</p><pre><code>加速比 = mean(speed_MTP) / mean(speed_baseline)
速度提升 (%) = (加速比 - 1) × 100
彙整 = exp(weighted_mean(log(加速比)))</code></pre><p>1.41× 約等於每秒輸出多 41%。固定輸出量時，僅生成階段的時間比例約為 1/1.41；這不是實測總等待時間的換算，prefill 與產出量仍會影響整體耗時。</p></section>'''
body+='<section id="related-work"><h2>公開實測怎麼說？這次補上什麼？</h2><p>以下是截至 2026-10-22 查閱的一手資料：官方實作說明、實測作者的原始報告，以及研究論文。這是針對本次問題的整理，不是完整文獻回顧；各來源硬體、量化、引擎與題目不同，數字不能直接排成效能排行榜。</p>'+table(['來源與條件','原作者報告／說明','如何對照本站'],[
['<a href="https://registry.ollama.com/blog/faster-gemma-4-mlx-mtp">Ollama 官方實測（2026-06-29）</a><br>M5 Max、Gemma 4 12B nvfp4、MLX／Ollama 0.31','Aider polyglot 程式代理測試，生成速度平均提升近 90%；實作會動態選草稿長度。','支持依工作負載調整的方向。本站是固定 N 的 llama.cpp／GGUF，助理題也不是完整 Aider 執行，不能視為重現其數字。'],
['<a href="https://github.com/Sunwood-ai-labs/gemma4-mtp-benchmark/blob/main/README.md">Sunwood-ai-labs 作者實測</a><br>M1 Max 64GB、LiteRT-LM、E4B','程式題估計 tok/s 約 1.87×；多任務單輪測試指出程式、JSON、擷取較受益，創意或極短題可能持平或變慢。','任務差異已有前例。本站補入諮商輔導領域及固定 N1–4、草稿 Q4/Q8；本站用引擎記錄的生成速率，並非字元換算的估計值。'],
['<a href="https://github.com/ecohash-ai/ecohash-benchmarks/blob/main/llm/speculative-decoding-qwen3.8-27b.md">EcoHash 作者實測（2026-08-19）</a><br>RTX PRO 6000、vLLM、Qwen 3.8 27B FP8','單流 K=3：數學 99.9、程式 78.9、聊天 76.9 tok/s；各自基準為 44.1、44.3、44.2。另測並行與每位置接受情形。','工作負載差異不限於 Gemma，程式也不是任何題組都最受益。本站增加 Apple Silicon 上的領域文字對照。K 與本站 N 都涉及草稿長度，實作計數方式仍需核對。'],
['<a href="https://ai.google.dev/gemma/docs/mtp/overview">Google Gemma 官方機制說明</a>','MoE 驗證多個 token 可能啟用更多專家，額外讀取權重會抵銷收益；硬體與批次大小會影響結果。','這提供解釋本站 MoE 高 N 收益下降的可能機制，但本站沒有直接量測專家載入成本。'],
['<a href="https://arxiv.org/abs/2402.01528">Decoding Speculative Decoding（NAACL 2025）</a>','在 LLaMA-65B、OPT-66B 的廣泛實驗中，草稿延遲是效能的重要因素；草稿語言模型能力不等同於加速能力。','屬一般 speculative decoding 研究，並非本次 Gemma/Qwen MTP 的直接驗證；提醒後續測試同時記錄接受率與計算成本。']])+'<div class="callout"><strong>本站的額外價值</strong><p>在同一台 M3 Ultra 80 核心 GPU／256GB、同一套測試流程下，把諮商輔導文字與助理程式題並列，提供六模型、草稿 N1–4 與可用 Q4/Q8 的對照。除了問「MTP 有沒有快」，也問「哪種工作該先試哪個 N」。公開逐次效能數值與重算程式，讓其他架設者可以核對；原題目含個資而未公開，所以尚不能完整重現原工作負載。</p></div><p>任務依賴性並非本站首次發現；領域素材、硬體及設定組合，是這批資料對既有實測的補充。</p></section>'
body+='<section id="task-evidence"><h2>固定 Q4、N=4：任務差異有多大？</h2><p>以下全部比較相同的草稿 Q 與 N，避免把「兩類任務各自挑最佳設定」的差別混進來。提升幅度各自以同模型、同題的不開 MTP 為基準；最後一欄是百分點差，不是 Agent 比輔導快多少百分比。</p>'+table(['模型','輔導文字提升','助理程式題提升','提升幅度相差'],[[r['model'],pct(task_gain(i,'counseling',4)),pct(task_gain(i,'agent',4)),f"{(task_gain(i,'agent',4)-task_gain(i,'counseling',4))*100:.1f} 個百分點"] for i,r in enumerate(R['by_model'])])+'<p>E4B 與 12B 的差距醒目，31B 也有相近程度的差距。若改看 N1→N4 的任務交互作用，三者分別約 +22.3%、+23.6%、+21.7%。因此可提出「較小模型值得測試依任務選 N」的部署假設，但目前並沒有模型越小、差異越大的單調趨勢。</p></section>'
body+='<section id="next-tests"><h2>下一輪，哪些驗證最能幫到社群？</h2><p>優先回答能改變架設決策的問題。下列是假設與建議設計，尚未執行；不是本站已證實的結論。</p>'+table(['優先方向／假設','怎麼驗證','對社群的價值'],[
['1 · 依任務選 N，可能比固定 N 更實用','每類先準備約 10–20 道獨立題目作探索起點（不是統計保證）；拆成選設定與驗證兩組。比較固定 N2、固定 N4、依任務選 N；在保留題與混合工作流測總耗時及品質。','提供可以重跑的領域題組與任務設定參考；即使結果不支持分流，也能知道固定 N 已足夠。'],
['2 · 可預測性可能比任務名稱更能解釋差異','以相同內容做自由文字、JSON、程式／固定格式等版本，盡量匹配輸入長度、輸出預算與採樣。記錄各 N 的草稿接受率、實際速度，若引擎可提供則加上草稿／驗證耗時。','分清楚是領域本身、輸出格式，還是計算成本在影響收益；避免把所有聊天或程式歸為同一種負載。'],
['3 · 小模型可能更值得按任務調校','優先擴充 E4B、12B 的獨立題目，並保留 31B 作對照；固定主模型量化與軟體版本。比較任務分流相對於最佳固定 N 的額外收益，不只比較兩條曲線距離。','檢驗小模型部署假設是否成立。要談大小規律，還需更多可比的同家族模型；MoE 啟用參數不宜直接當成 dense 大小。'],
['4 · 最佳 N 可能隨 context、並行及快取改變','將同一核心任務搭配不同長度的背景，控制輸出要求；分別測單請求及實際服務並行，區分冷／暖快取。記錄首字等待、每請求延遲與整體吞吐量。','把單機單流結果接到真實服務需求；識別什麼負載下應降低 N 或關閉 MTP。'],
['5 · Q8 的收益可能取決於接受率能否抵銷成本','先核對草稿 GGUF 型別、檔案大小與雜湊，特別是本紀錄 E4B Q4/Q8 都標成 94MB 的疑點。再在相同題目、N、採樣下交錯比較 Q4/Q8。','讓草稿量化比較可追溯；分辨 Q8 何時值得多用記憶體，而非只看接受率高低。']])+'<h3>建議共用的測試規格</h3><p>公開題目應使用全新合成或確實去識別的內容，保留領域術語、格式與長度分布；先確定沒有學生個資、諮商紀錄或密碼。記錄題組版本、模型／草稿雜湊、引擎 commit、硬體、採樣、輸出上限與實際輸出量。每題各設定可先重跑 3–5 次、跨批次並打散順序，另外保留品質檢查與工具成功率。</p><p>測試順序隨機化、首字等待及品質評分需要另增工具；本站公開 runner 目前仍是原始固定順序。社群共享優先提供逐次數值、題組規格與重算程式；受保護素材及其輸出留在本地。這一輪最有價值的交付，是別人能用自己素材重跑、也能用共同合成題組對照的測試方法。</p></section>'
source_cards=''
for i,(mid,meta) in enumerate(META.items()):
    drafts='<br>'.join(E(d['filename'])+' — '+E(d['label']) for d in meta['drafts'])
    source_cards+=f'<article class="panel"><h3>{E(R["by_model"][i]["model"])}</h3><p><strong>主模型量化：{meta["main_quant"]}</strong></p><p class="file"><a href="{meta["url"]}">{E(meta["repository"])}</a></p><p class="file">主模型檔案：<br><code>{E(meta["main_file"])}</code></p><p class="file">草稿檔案（測試紀錄標籤）：<br>{drafts}</p></article>'
body+='<section id="model-sources"><h2>實際使用的 Unsloth 模型</h2><p>下列來源依提供的 GGUF 檔名，對照 Unsloth 的 Hugging Face 檔案清單（2026-10-22 查核）。四個 Gemma 4 都是 it-qat 版本；Qwen 兩個模型分別使用 8-bit 與 6-bit 系列的 Dynamic 量化。保留完整 UD 標籤，不把混合精度檔案簡化成每個權重都固定為相同位元數。</p><div class="two">'+source_cards+'</div><p>Flash Next 的 UD-Q6_K_XL 為六個分片，表列第一個分片名稱；載入時需有完整檔案組。主模型來源已按檔名核對，但沒有取得本地權重 SHA-256 與下載 revision，因此不宣稱與目前上游檔案位元一致。草稿量化依本地設定標籤呈現；Gemma 無量化後綴的草稿檔與 Q8 檔，仍需檢查 GGUF metadata 才能確認實際型別。</p><p>Gemma 4 12B QAT 未列於後來提供的服務設定，其型號與量化來自 benchmark 的 models_config.json。<a href="data/model_sources.json">下載模型來源與檔名對照</a>。</p></section>'
body+='<section><h2>另提供的服務設定：與測試條件分開看</h2><p>以下摘要來自專案發起人另提供的服務設定，並非這 1,250 次 benchmark 的執行紀錄。它包含更長的 context 與多個並行 slot，不能直接套用本站加速百分比。為保護本機資訊，僅保留設定值與模型名稱，不公開個人路徑。</p>'+table(['模型','服務 context c','並行設定（原鍵名）','MTP N'],[['Gemma 4 E4B QAT','131,072','parallel=4','3'],['Gemma 4 26B A4B QAT','262,144','parallel=2','2'],['Gemma 4 31B QAT','131,072','全域 parallel=3','4'],['Qwen 3.8 27B','524,288','np=4；全域 parallel=3','4'],['Qwen 3.8 Flash Next','524,288','parallel=2','該段未設定 MTP']])+'<p>全域設定含 f16 K/V cache、continuous batching、kv-unified=true、cache-ram=16384、fit=on、fit-target=16384、fit-ctx=8192 及 mmap。Flash Next 另外設 kv-unified=false。Gemma 4 E4B QAT 的 ubatch=512，其餘列出的測試模型多為 2048；benchmark 則統一使用 context 16384 與 batch/ubatch 2048。並行鍵名 np 與 parallel 的優先順序需依實際服務版本確認，表格不推定衝突時的有效值。</p><p>其他服務模型（Qwen 3.6、Muse、embedding 與 reranker）未參與本次測試，不列入效能結論。這份服務設定也不等同於本站建議：例如 E4B 原服務採 N3，而本次輔導題的最快觀察值為 N2。</p></section>'

body+='<section><h2>七個問題，可以回答到哪裡？</h2>'+table(['問題','本次能回答的範圍'],[['1. Context','長度與題目內容混淆；window 固定，無法識別獨立主效果。'],['2. MTP','Q4 N1–4 平均提升 '+pct(R['main_mtp_q4'])+'；是本批資料的描述性平均。'],['3. Q','五模型同條件配對：Q8 相對 Q4 '+pct(R['q8_over_q4'])+'。'],['4. N','共同 Q4 設計 N3 最高，但與 N2、N4 接近。'],['5. N × 任務','N1→N4 的 Agent/輔導比值之比為 1.1767。'],['6. MoE × N','MoE/非 MoE 的 N1→N4 比值之比為 0.7573；不能歸因架構本身。'],['7. N × 任務 × 大小','可比較各模型的曲線，無法單獨識別模型大小；最佳 N 是結果衍生值。']])+'</section>'
body+='<section><h2>MTP 與量化的模型差異</h2>'+table(['模型','Q4 MTP 平均提升','Q8 相對 Q4'],[[r['model'],pct(r['mtp_q4']),pct(r['q8_over_q4']) if 'q8_over_q4' in r else '未測'] for r in R['by_model']])+'<p>主模型固定使用的量化：Gemma 四模型為 UD-Q4_K_XL，Qwen 3.8 27B 為 UD-Q8_K_XL，Flash Next 為 UD-Q6_K_XL。它們不是主模型量化一致的對照實驗。</p></section>'
body+='<section><h2>N × 任務的交互作用</h2><p>交互作用不只問哪類任務快，而是「提高 N 後，兩類任務的收益是否不同」。以 N1 為參考，計算 [(Agent N / Agent N1) / (輔導 N / 輔導 N1)] − 1。</p>'+table(['N','整體提升','輔導提升','Agent 提升','任務交互作用 vs N1'],[[r['n'],pct(r['all']),pct(r['counseling']),pct(r['agent']),pct(r['task_interaction_vs_n1'])] for r in effects])+'<p>五個 Q 完整模型改以 Q4/Q8 等權重：N1–4 分別提升 '+ '、'.join(pct(x['gain']) for x in R['n_complete_q_average'])+'，N2 略高於 N3。最佳整體 N 依模型組成與權重而異。</p></section>'
body+='<section><h2>MoE × N：觀察到的組別差異</h2>'+chart([('MoE',[(r['moe']-1)*100 for r in effects]),('非 MoE',[(r['dense']-1)*100 for r in effects])],'MoE 與非 MoE 模型的 MTP 速度提升')+table(['N','MoE 提升','非 MoE 提升','組別交互作用 vs N1'],[[r['n'],pct(r['moe']),pct(r['dense']),pct(r['moe_interaction_vs_n1'])] for r in effects])+'''<p>MoE 組為 Gemma 4 26B A4B QAT 與 Qwen 3.8 Flash Next，其他四個歸為非 MoE。架構分類參考 <a href="https://ai.google.dev/gemma/docs/core.md">Google 模型概覽</a>、<a href="https://developers.googleblog.com/gemma-4-12b-the-developer-guide/">Gemma 4 12B QAT 說明</a>、<a href="https://huggingface.co/Qwen/Qwen3.8-27B">Qwen 3.8 27B 模型卡</a>及 <a href="https://docs.nvidia.com/nemo/automodel/nightly/model-coverage/large-language-models/qwen/qwen3-8-flash-next">NVIDIA 架構文件</a>。MoE 僅兩模型，且家族、大小、量化、草稿成本同時改變；不能把差異視為架構本身的因果效果。</p></section>'''
body+='<section><h2>Context：只能做伴隨題目變化的比較</h2><p>baseline 的輔導三題依序為短、中、長輸入。下表呈現輸入 tokens／生成 tok/s。最長題相對最短題慢約 1.8%–5.9%，但內容與輸出長度也不同，不能稱為純粹的長度效果。</p>'+table(['模型','短題','中題','長題'],[[R['context'][i]['model']]+[f'{int(x["tokens"]):,} / {x["speed"]:.2f}' for x in R['context'][i:i+3]] for i in range(0,18,3)])+'</section>'
body+='<section><h2>模型大小與三因子對比</h2><p>大小與模型身分綁定。E4B 的有效參數、MoE 總參數與啟用參數，以及權重檔案 GB，不能混為同一個大小變項。下表列出各模型「N4 vs N1 的 Agent/輔導交互作用」；兩模型的比值再相除，可得到模型間三重對比，但不代表大小的獨立效果。</p>'+table(['模型','N4 vs N1 任務交互作用'],[[r['model'],pct(r['interaction_n_vs_1'][3])] for r in R['threeway_descriptive']])+'<p>例如 Gemma 4 31B QAT 相對 E4B 的上述交互作用比值為 0.99496，差約 −0.50%。這是描述性三重對比，不能用來判定統計顯著或證明沒有交互作用。</p></section>'
body+=f'''<section><h2>穩定度、資料限制與下一輪測試</h2><ul><li>排除各條件第一次執行後，Q4 平均提升 {pct(R['main_mtp_q4_warm'])}；12 個模型×任務組合的最佳 Q4 N 均不變。</li><li>有 14 個條件的第一次執行仍有快取，不能一律視為完全 cold。</li><li>輸出範圍為 1,022–4,096 tokens；181 次恰達 4,096 上限，但未存停止原因，無法逐筆確認截斷。</li><li>Q4 MTP 的平均 wall time 比值下降約 28.7%，輸出量平均差約 −0.15%；個別條件的產出量仍有差異。</li><li>條件內生成速度的變異係數中位數 1.68%、最大 14.02%。最快與次快相差很少時，應在新批次再測。</li><li>五次執行是技術重複，不是五道獨立題目。本報告不將 1,250 筆當成獨立樣本計算 p 值或一般化信賴區間。</li><li>原 runner 固定順序測試，未指定 seed，且沒有硬體溫度、功耗或背景負載紀錄。測量不能排除批次、順序等影響。</li><li>接受率不是回答正確率。未評分內容品質，也沒有完整 Agent 工具執行的成功率資料。</li></ul><p>下一輪應讓每類任務有多道獨立題目，每題交叉多種輸入長度，控制輸出預算，隨機化設定順序並跨批次重複；分開測 cold 與 warm。先用一組題目挑 N，再在保留題目驗證。模型大小或架構效果需要更多可匹配的模型，不能只增加同一設定的重跑次數。</p></section></div>'''
page('analysis.html','技術與分析',body)

body=f'''<div class="page-title"><div class="eyebrow">Open metrics / Reproducible analysis</div><h1>資料與程式碼</h1><p class="lead">公開計算所需的數值與方法，保留原題目的隱私。你可以重算本頁結果，也可以用全新題目執行自己的測試。</p></div><section><h2>下載公開資料</h2><div class="downloads"><a class="download" href="data/benchmark_metrics.json" download>逐次測量數值 · JSON<small>1,250 次執行；只含模型設定、通用題號與效能數值。</small></a><a class="download" href="data/analysis.json" download>分析結果 · JSON<small>主效果、交互作用、最佳設定與敏感度分析。</small></a><a class="download" href="data/cell_summaries.json" download>條件彙整 · JSON<small>250 個條件的平均、標準差與 warm-only 速度。</small></a><a class="download" href="data/environment.json" download>環境紀錄 · JSON<small>硬體、推論環境與測試協定；已移除個人路徑。</small></a></div></section><section class="two"><div class="panel"><h2>重算既有結果</h2><p>下載儲存庫後，使用 Python 3 的標準函式庫即可。這會從公開數值重建分析與網站，不會啟動模型。</p><pre><code>python scripts/analyze.py
python scripts/build_site.py
python scripts/validate.py</code></pre><a href="{repo}/tree/main/scripts">瀏覽程式碼 →</a></div><div class="panel"><h2>執行新的效能測試</h2><p>先修改模型設定檔中的路徑，再指向自己的 llama-server。範例題目全部是新寫的合成內容，不能重現原測試的文字與長度。</p><pre><code>export LLAMA_SERVER=/path/to/llama-server
export BENCH_MODELS=/path/to/models.json
export BENCH_PROMPTS=/path/to/prompts.json
export BENCH_OUTPUT=/path/to/new-results
python scripts/run_benchmark.py</code></pre><p class="small">每批測試使用新的輸出目錄，以免舊版 runner 的續跑判定混用不同題目或環境。完整模型測試會使用本機運算與記憶體資源。</p></div></section><section class="prose"><h2>哪些內容沒有公開？</h2><p>原始五題的實際 prompt 均未上傳，範例 1–3 的學生與晤談內容也未納入。所有模型輸出、推理文字、執行 log、舊報告自由文字及個人檔案路徑均不在公開範圍。公開 JSON 是從允許欄位重新產生，不是把原檔改名。</p><p>這保留了效能數值分析的可重算性，但不具備原始工作負載的完整可重現性。公開合成題目僅示範程式格式，沒有被用來產生本站結果。</p><h2>共同作者</h2><p>gregorytsai、OpenAI Codex、Gemini 3.8 Flash。</p><p>依專案發起人指定共同署名。AI 名稱標示參與工具，本站結果仍應以公開數值與分析方法核對。</p><h2>程式來源與修改</h2><p><code>run_benchmark.py</code> 改編自提供的原測試程式，將本機路徑改為環境變數、改用合成題目、將新結果寫到獨立目錄，並移除寫死的硬體與版本宣告。分析與靜態頁面產生器為本次整理新增。</p><p>未在本次整理時重跑 Mac 的模型推論。已做的檢查包含 Python 語法、公開數值一致性、分析重算、連結及網頁顯示；這些不能取代實機效能驗證。</p><h2>檔案完整性</h2><p><a href="data/manifest.json">公開檔案 SHA-256 清單</a>可用於核對下載內容。<a href="data/validation.json">驗證摘要</a>記錄公開資料與頁面的靜態檢查。</p><a class="button" href="{repo}">前往 GitHub 儲存庫 ↗</a></section>'''
page('resources.html','資料與程式碼',body)
print('Built index.html, analysis.html, resources.html and chart-data.js')

(ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join('  <url><loc>'+SITE+path+'</loc></url>\n' for path in ['', 'analysis.html', 'resources.html'])+'</urlset>\n',encoding='utf-8')

import sys
sys.dont_write_bytecode = True
from build_english import build_english
build_english()
