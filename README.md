# Mac Studio M3 Ultra 256GB · 80 核心 GPU｜MTP 實測與設定指南

[開啟圖文網站](https://gregorytsai.github.io/mac-studio-m3-ultra-mtp-benchmark/)

六模型、五道題目、1,250 次執行的本機生成速度分析。主頁提供設定速查與互動比較；技術頁保留方法、來源差異與限制。

## 本次值得追蹤的觀察

同模型、同草稿 Q4 下，諮商輔導文字與助理程式題會有不同的 N 曲線。E4B、12B 的差異清楚，31B 也有類似現象；可提出「較小模型值得測試依任務選 N」的部署假設，但尚無模型越小差異越大的規律。

主頁新增小模型對照圖與領域試測建議；技術頁整理 Google、Ollama、Sunwood、EcoHash 與 NAACL 研究的一手來源，並列出五個值得社群驗證的方向。任務依賴性已有公開實測，本站的補充是同一台 Mac 上的領域文字、六模型與 Q／N 對照，並非宣稱首次發現。

## 閱讀順序

- `index.html`：淺顯圖解與模型／任務設定參考。
- `analysis.html`：七項效果、統計方法、執行條件與限制。
- `resources.html`：數值下載、程式與資料公開範圍。

## 重算分析與頁面

Python 3，僅使用標準函式庫：

```sh
python scripts/analyze.py
python scripts/build_site.py
python scripts/validate.py
python -m http.server 8765
```

開啟 `http://localhost:8765`。驗證程式第一次執行前，發布流程已建立 manifest 與 validation 檔案；它們也隨儲存庫提供。

## 新測試

`scripts/run_benchmark.py` 是原測試 runner 的公開改編版。修改 `scripts/models_config.example.json` 中的模型路徑，使用 `LLAMA_SERVER`、`BENCH_MODELS`、`BENCH_PROMPTS`、`BENCH_OUTPUT` 環境變數指定執行檔、設定、題目與新結果目錄。每個新批次使用獨立輸出目錄，避免續跑混用。

原 runner 保留逐設定／逐題的固定測試順序，未新增隨機 seed 或隨機化設計；程式語法驗證不代表在目前 llama.cpp 版本上實機驗證。

## 隱私與可重現性

原始 prompt（包含範例 1–3）、模型回答、推理內容及 log 均不公開。效能 JSON 從白名單欄位重建，題目只保留通用題號與任務分類；個人路徑已移除。`prompts.synthetic.json` 全部是新寫的合成示例，未用於產生本網站數據，也無法重現原始文字工作負載。

公開數值可以重算統計結果。5 次執行是技術重複，不是 5 道獨立題目；沒有將 1,250 筆當作獨立樣本做顯著性檢定。最佳設定只適用本次觀察，需用自己的題目與品質要求確認。

## 發布

GitHub Pages 使用 `main` 分支根目錄，無建置框架、外部字型或追蹤服務。修改資料後先重跑分析、產生器及驗證，再提交產生的 HTML／JSON。

## 共同作者

gregorytsai、OpenAI Codex、Gemini 3.8 Flash。依專案發起人指定共同署名；AI 名稱標示參與工具。
