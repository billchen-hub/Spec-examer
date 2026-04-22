# Spec Benchmark Test — Engineering Handover

> 目標讀者：接手這個專案的工程師。
> 這份不是 user guide — 使用者操作面看 [`USER_GUIDE.md`](USER_GUIDE.md)。
> 這份是給**要改程式、加功能、debug、或把它搬到其他 LLM 後端**的人看的。

---

## 1. 這個系統在做什麼

一句話：**對 spec 文件出考題，讓地端 AI 作答，再用另一個 AI 當裁判評分，產出改善建議。**

三個 AI 角色，責任完全分離：

| 角色 | 實作 | 可替換 |
|---|---|---|
| Examiner（出題者） | Claude Code session 或 Nexus AI（`--generate`） | 是 |
| Examinee（答題者） | Nexus AI | 是（換 share_code 即可） |
| Judge（裁判） | Nexus AI | 是（換 share_code 即可） |

**關鍵設計決策（進來前要知道）：**

1. **出題和考試是兩個獨立流程**。題庫是 JSON 檔，可以重複用、手動編輯、跨 session 累積。
2. **Examinee 不需要帶 spec 給它**。Nexus 那邊有自己的 RAG，這邊只負責把題目丟過去、把答案收回來。
3. **Prompt 全部走 YAML 模板**（`prompts/*.yaml`），程式碼裡完全沒有 hardcode prompt。改出題風格、評分標準、答題口吻，改 YAML 就好，**不用碰 Python**。
4. **BAT 包裝層**（`setup.bat` / `run_exam.bat`）是給不會用 CLI 的同事雙擊用的。純 ASCII、英文提示，不是因為我們不用中文，是因為 Windows cmd.exe 的編碼問題（詳見 §11）。

---

## 2. 程式進入點與三種執行模式

所有模式都從 `exam_runner.py::main` 進入，由 argparse 分流：

```
exam_runner.py
 ├── --generate PATH [PATH ...]       → run_generate()       出題
 ├── --answer-only                    → run_answer_only()    只答題，不評分
 └── (無 flag)                        → run_exam()           答題 + 評分 + 報告
```

**三種模式各自對應的使用情境：**

| 模式 | 何時用 | 輸出 |
|---|---|---|
| `--generate` | 想讓 Nexus 自動出題（人不在 Claude Code 前面時） | `question_bank/<stem>_<N>q_<ts>.json` |
| `--answer-only` | 把答題和評分拆在不同機器（有 API key 的機器答、有 Claude Code 的機器評） | `results/answers_<ts>.json` |
| 預設 | 一站式：答題 + 評分 + HTML/JSON/MD 三份報告 | `results/exam_<ts>.{html,json}` + `exam_<ts>_suggestions.md` + `answers_<ts>.json`（備用重評分） |

**注意 `--answer-only` 的設計動機**：Nexus API 走公司內網，有時只有特定機器能打；評分用 Claude Code 不佔 API 額度。拆成兩階段就是為了這個 workflow。

---

## 3. 檔案責任矩陣

```
spec benchmark test/
├── exam_runner.py          CLI 主程式；argparse、三種模式的流程控制
├── spec_loader.py          讀 spec（.pdf/.md/.txt/.log，支援檔案+資料夾混合輸入）
├── examiner.py             Claude Code session 出題時用的輔助（list_specs + save_question_bank）
├── nexus_client.py         Nexus REST API 客戶端（sync + async 兩版）← Hermes 遷移的主要替換點
├── judge.py                裁判邏輯：單題評分 + 綜合建議
├── prompt_loader.py        YAML 模板載入 + {{var}} 替換
├── report_generator.py     產 HTML / JSON / suggestions.md 三種報告
│
├── config.yaml             認證、路徑、預設參數
├── prompts/                Prompt 模板（3 個角色各一）
│   ├── examiner.yaml       出題規則、題型比例、JSON 輸出 schema
│   ├── examinee.yaml       答題口吻、引用章節的要求
│   └── judge.yaml          評分權重、JSON 輸出 schema；含 overall_template
├── templates/report.html   HTML 報告的 Jinja2 模板（自包含，不需要外部 CSS/JS）
│
├── specs/                  放 spec 原文（.pdf / .md / .txt / .log）
├── question_bank/          產出的題庫 JSON
├── results/                考試結果（HTML / JSON / suggestions.md / answers.json）
│
├── tests/                  pytest；30 個測試
├── run_exam.bat            Windows 雙擊進入點（純 ASCII、delayed expansion）
├── setup.bat               Windows pip install 進入點
└── USER_GUIDE.md           使用者操作面文件
```

每個檔案做什麼、別做什麼的**邊界**：

- `exam_runner.py` **只做流程編排**。不要把解析 Nexus 回應、評分邏輯塞進來。
- `spec_loader.py` **只讀檔，不跟 AI 對話**。測試可以脫離任何網路環境跑。
- `nexus_client.py` **只是 HTTP 封裝**。不懂什麼是 examiner / examinee / judge — 它只知道「打 API」。要換 LLM 後端就改這一個檔。
- `prompt_loader.py` **只做模板載入 + 字串替換**。不引用 jinja2（jinja2 只在 report_generator 用）。替換規則是簡單的 `{{var}}` → value。
- `judge.py` **只處理裁判那一塊**。Nexus 回應的 JSON parse 容錯在這裡做（`_parse_response`），不要散到 exam_runner。

---

## 4. 資料流（end-to-end）

**出題流程（`--generate`）：**

```
使用者 CLI
  └─ spec_loader.load_spec_content(paths)
      └─ collect_spec_files()   掃資料夾、dedup（realpath）
      └─ read_spec_file() 每檔
          ├─ _read_pdf_file()   pypdf
          └─ _read_text_file()  UTF-8 → latin-1 fallback
      └─ 組合：--- FILE: <name> ---\n<text>\n\n...
  └─ prompt_loader.render("examiner", {num_questions})
  └─ full_prompt = examiner_prompt + "\n\n--- SPEC CONTENT ---\n\n" + combined
  └─ NexusClient.generate_response_sync(share_code, history=[{role:1, content: full_prompt}])
  └─ _parse_questions_response(text)      多策略 JSON 抽取
  └─ 寫 question_bank/<stem>_<N>q_<ts>.json
```

**考試流程（預設模式）：**

```
使用者 CLI
  └─ load question_bank JSON
  └─ select_questions(mode, random_count)    full 或 random
  └─ for each question:
      ├─ examinee_prompt = render("examinee", {question})
      ├─ NexusClient (examinee) .generate_response_sync()
      ├─ 寫進 answers.json（每題都即時落盤 → 中斷後不會丟）
      ├─ Judge.score_answer(q, answer)
      │   └─ render("judge", {...})
      │   └─ NexusClient (judge) .generate_response_sync()
      │   └─ _parse_response()     regex 抓 {...score...}，parse 失敗 fallback 0 分
      └─ 累積 results
  └─ Judge.generate_overall_suggestion(results, avg)
  └─ ReportGenerator.generate_all(data)
      ├─ save_json()          結構化資料
      ├─ save_html()          Jinja2 渲染 report.html
      └─ save_suggestions()   Markdown
```

**注意 `answers.json` 每題即時落盤**是刻意的 — Nexus API 偶爾 timeout 或公司網路掉線，即時落盤可以讓我們用 `--answer-only` 模式繼續跑、或從 JSON 手動補評分。

---

## 5. `spec_loader.py` 設計重點

這是 2026-04-22 新寫的模組（commit `96d4f04`），是 `--generate` 能接受**多檔、多資料夾、PDF、MD、TXT、LOG 混合輸入**的核心。接手前至少要知道這幾個設計決策：

### 5.1 支援的輸入形狀

```python
load_spec_content([
    "specs/chapter1.md",                  # 檔案
    "specs/ufs spec md/",                 # 資料夾（遞迴）
    "specs/appendix.pdf",                 # PDF
    "/absolute/path/extra/",              # 絕對路徑也 OK
])
```

### 5.2 去重用 `realpath` 不是 `abspath`

```python
def _add(path):
    key = os.path.realpath(path)   # 不是 abspath
    if key in seen: return
    ...
```

**為什麼**：Windows junction / symlink 下，同一份檔案透過不同路徑到達時，`abspath` 看起來不同但 `realpath` 會解開到同一處。之前 code review 抓到的 major issue。

### 5.3 `_SKIP_DIRS` 只在「遞迴子層」生效

```python
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}

for dirpath, dirnames, filenames in os.walk(path):
    dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
```

**意圖**：使用者把 `tmp_path` 當輸入根時，裡面的 `.git` 會跳過；但如果使用者**直接**把 `.git` 當輸入，我們尊重他的意圖，照樣掃。這個邊界有測試保護（`TestSkipDirsBoundary`），改之前先看那份測試。

### 5.4 全空內容要炸

```python
if non_empty == 0:
    raise SpecLoadError("All N spec file(s) produced no extractable text ...")
```

**為什麼**：掃描版 PDF（沒跑過 OCR）`pypdf` 抽不到文字，會回空字串。如果全部檔案都空，我們**拒絕**送空 prompt 給 AI（會浪費 API、產垃圾）。個別檔案空會 warning log 但不阻斷。

### 5.5 文字檔編碼 fallback

```python
try:
    with open(path, "r", encoding="utf-8") as f: ...
except UnicodeDecodeError:
    with open(path, "r", encoding="latin-1") as f: ...
```

不是完美解，但 latin-1 是 byte-preserving 的 fallback — 讀進來字元會怪，但至少不會 crash。如果將來要處理 cp950 log 檔，在這裡加。

---

## 6. Nexus → Hermes 遷移路徑

公司未來要切到 Hermes agent + Qwen 3.5。**不用重寫，就改一個檔**：

### 6.1 替換點就是 `nexus_client.py`

```python
class NexusClient:
    def __init__(self, key): ...
    def generate_response_sync(self, share_code, history, ...) -> str: ...
    async def generate_response(...) -> str: ...   # 目前沒人用，可留可刪
    async def upload_file(path) -> int: ...        # 目前沒人用
```

**實際被呼叫的只有 `generate_response_sync`**（`exam_runner.py` 和 `judge.py` 各用一次）。

### 6.2 遷移 checklist

1. 建 `hermes_client.py`（或直接改 `nexus_client.py`）。保留 **`generate_response_sync(share_code, history, system_prompt=None, files=[]) -> str`** 這個簽章。
2. `share_code` 在 Hermes 裡是什麼概念？若是 agent ID，直接對映；若不是，可以改成 agent config path。`config.yaml` 的 credentials 區塊要跟著調。
3. Payload 格式：現在是 `{shareCode, prompt: "<<<msg>>>", previousMessage, files}`。Hermes 若走 OpenAI-compatible，改成 `{messages: [...]}` 即可。
4. 回傳值要保持**純字串**，不要回 dict。上游 `_parse_*_response()` 預期 regex / json.loads 一個字串。
5. 錯誤分支要回 `"[ERROR] ..."` 開頭的字串，不要 raise — `exam_runner.py` 有 `startswith("[ERROR]")` 判斷。
6. 保留 timeout handling（目前 sync 版 120 秒）。

### 6.3 為什麼不現在就抽象成 `LLMClient` interface

故意的。現在只有一家供應商，抽象會讓讀者多跳一層找不到實作。等真的要接第二家的時候再 extract — YAGNI。

---

## 7. Prompt 模板怎麼擴展

所有 prompt 在 `prompts/*.yaml`，結構都長這樣：

```yaml
name: "<role name>"
description: "<一句話>"
template: |
  <prompt 主體，用 {{variable}} 寫變數>
```

`judge.yaml` 多一個 `overall_template:` 欄，`PromptLoader.render(..., template_key="overall_template")` 會切換。

**要加新角色（例如 critic、fact-checker）的流程**：

1. 新增 `prompts/<role>.yaml`，照同樣結構。
2. `exam_runner` 或 `judge` 裡呼叫 `prompt_loader.render("<role>", {...})`。
3. 不用動 `prompt_loader.py` — 它的替換規則對任何 `{{name}}` 都適用。

**變數替換規則（`prompt_loader.py::_substitute`）：**

- regex `\{\{(\s*\w+\s*)\}\}`
- 找不到對應 key 的 placeholder **會原樣保留**（不會 KeyError）
- 只支援簡單 key，不支援點語法 (`{{user.name}}` 不會 work)
- 不是 jinja2，不支援 `{% for %}` 之類

如果將來要支援條件分支，可以考慮改用 jinja2（`report_generator.py` 已經引了 jinja2），但**目前的刻意選擇是極簡**：prompt 的邏輯應該用自然語言寫，不是用模板分支。

---

## 8. 資料格式（JSON Schema）

### 8.1 `question_bank/<file>.json`

```jsonc
{
  "metadata": {
    "spec_file": "ufs_spec.pdf",                // 單檔時檔名，多檔時 "N files"
    "spec_inputs": ["specs/ufs_spec.pdf"],      // --generate 傳進來的原始路徑（多檔用）
    "source_files": ["ufs_spec.pdf"],           // 實際讀到的 display 名（多檔用）
    "generated_at": "2026-04-22T10:30:00",
    "generated_by": "nexus",                    // 或 Claude Code 出題時不會有這個欄位
    "examiner_share_code": "XXXX",              // 僅 Nexus 出題時
    "total_questions": 100
  },
  "questions": [
    {
      "id": 1,
      "type": "qa",                             // "qa" 或 "multiple_choice"
      "difficulty": "easy|medium|hard",
      "question": "...",
      "reference_answer": "...",                // qa 題才有
      "options": ["A) ...", "B) ...", ...],     // mc 題才有
      "correct_answer": "C",                    // mc 題才有
      "explanation": "...",                     // mc 題才有
      "source_section": "Section 7.1.2"
    }
  ]
}
```

向後相容：舊題庫沒有 `spec_inputs` / `source_files` 也能讀 — `exam_runner` 只看 `questions` 陣列。

### 8.2 `results/answers_<ts>.json`（`--answer-only` 或全考的即時落盤）

```jsonc
{
  "exam_id": "answers_20260422_103000",
  "timestamp": "2026-04-22 10:30:00",
  "question_bank": "ufs_spec_v4.1_100q.json",
  "mode": "full|random",
  "total_questions": 100,
  "completed_questions": 47,                    // 即時更新；斷線後可看這個判斷從哪續
  "examinee_share_code": "XXXX",
  "answers": [
    { "question_id": 1, "examinee_answer": "..." },
    ...
  ]
}
```

### 8.3 `results/exam_<ts>.json`（完整報告）

```jsonc
{
  "exam_id": "exam_20260422_103000",
  "timestamp": "2026-04-22 10:30:00",
  "config": {
    "question_bank": "ufs_spec_v4.1_100q.json",
    "mode": "full",
    "total_questions": 100,
    "examinee_share_code": "XXXX",
    "judge_share_code": "YYYY"
  },
  "average_score": 72.4,
  "results": [
    {
      "question_id": 1,
      "type": "qa",
      "difficulty": "medium",
      "question": "...",
      "options": null,
      "reference_answer": "...",
      "examinee_answer": "...",
      "score": 80,
      "judge_feedback": "...",
      "improvement_suggestion": "..."
    }
  ],
  "overall_suggestion": "... 可以直接當作 system prompt 使用 ..."
}
```

---

## 9. 測試

```bash
python -m pytest tests/ -v
```

目前 **30 個測試**，分佈：

| 檔案 | 數量 | 涵蓋 |
|---|---|---|
| `test_spec_loader.py` | 19 | 檔案收集、去重、skip_dirs 邊界、UTF-8 / latin-1、PDF 空內容、混合輸入 |
| `test_exam_runner.py` | 若干 | select_questions、derive_bank_name、parse_questions_response |
| `test_prompt_loader.py` | 若干 | YAML 載入、`{{var}}` 替換、缺漏變數處理 |
| `test_report_generator.py` | 若干 | JSON / Markdown 產出、HTML 渲染 |

**測試原則（接手後請保持）：**

- **不 mock Nexus API**。測試完全不能需要網路。要驗 HTTP 行為就 mock `requests.post`。
- **`spec_loader` 相關測試必須用 `tmp_path`**，不要寫死路徑。
- **改 `_SKIP_DIRS` 前先跑 `TestSkipDirsBoundary`**。那份測試**故意**把 `.git` 當輸入根 — 說明「使用者明確傳進來時就照掃」是 contract，不是 bug。
- **空 PDF 的行為有測試保護**（`test_pdf_with_no_extractable_text_returns_empty` + `test_all_empty_files_raise`）。個別檔案空回空字串，全部空才 raise。

---

## 10. Config 與 credentials

`config.yaml` 分三塊：

```yaml
nexus:          # base_url，通常不用動
credentials:    # API key 和三個角色的 share_code
exam:           # 預設題庫、模式、題數
paths:          # 四個主目錄（specs / question_bank / results / prompts）
```

**credentials 有兩種形式（向後相容）：**

新格式（共用 API key）：
```yaml
credentials:
  api_key: "..."
  examiner: { share_code: "..." }
  examinee: { share_code: "..." }
  judge: { share_code: "..." }
```

舊格式（每角色自己的 key）：
```yaml
credentials:
  examinee: { user_key: "...", share_code: "..." }
  judge: { user_key: "...", share_code: "..." }
```

`get_api_key()` 會先找 `credentials.api_key`，找不到退回每角色的 `user_key`。新開專案用新格式。

**config.yaml 絕對不要 commit 真 key**。Git repo 目前的 `config.yaml` 是預設樣板（key 都是 `YOUR_API_KEY` placeholder），交接時請告知同事本地填好後不要 commit。

---

## 11. 已知限制與 Debug Tips

### 11.1 Windows cmd.exe 編碼雷

- **`.bat` / `.cmd` / `requirements.txt` 一律純 ASCII**，不可放中文或 em-dash。pip 在 Windows 用系統預設（cp950/cp936）讀 `requirements.txt`，遇到 UTF-8 非 ASCII 會 crash。
- `.bat` 裡 `if` block 內要用變數值的話，**必須** `setlocal EnableDelayedExpansion` 配 `!var!`（不是 `%var%`）。之前 code review 抓到這個 bug。

### 11.2 PDF 無 OCR

`pypdf` 只抽 embedded text，掃描版 PDF 會回空。log 裡會看到：

```
WARNING: No extractable text in PDF: foo.pdf (scanned/image-only PDF? consider OCR)
```

遇到這種 spec 目前的解法是**請使用者先跑 OCR 轉成 MD**。在 `spec_loader.py` 加 OCR 是可能的（`pytesseract` + `pdf2image`），但**會引入 Poppler / Tesseract 外部相依**，目前不做。

### 11.3 Nexus API 超時

- Sync 版 timeout 120 秒，async 版 60 秒。
- Timeout 會回 `"[ERROR] Nexus API 請求逾時，請稍後再試。"` 字串（**不 raise**）。上游用 `startswith("[ERROR]")` 判斷。
- 出題（`run_generate`）timeout 的話會把原始 response 寫到 `question_bank/raw_response_<ts>.txt` 供 debug。

### 11.4 Nexus 回應 JSON 格式不穩

LLM 有機率回 markdown code fence、多一段解釋、或少一個大括號。抽 JSON 是多策略 regex（`_parse_questions_response` 和 `judge._parse_response`）。如果 parse 失敗：
- 出題 → 回傳 `None`，raw response 留在檔案裡。
- 評分 → score=0，feedback 塞 raw 前 500 字，不會中斷整場考試。

### 11.5 中途掉線怎麼續

`answers.json` 每題即時落盤（`_save_json_atomic`）。掉線後可以：
1. 看 `results/answers_<ts>.json` 的 `completed_questions` 知道斷在哪。
2. 手動 slice 題庫把已答過的剔掉。
3. 用新的 bank 重跑 `--answer-only`。
4. 最後人工合併兩份 answers.json，交給 Claude Code 一次性評分。

**沒有自動化這個續跑流程** — 因為使用情境少，不值得複雜化。

---

## 12. 擴展入口

想要**加功能**，從這幾個點進：

| 想做 | 改哪 |
|---|---|
| 支援新的 spec 格式（如 `.docx`） | `spec_loader.py::SUPPORTED_EXTS` + 加新的 `_read_xxx_file()` |
| 改出題風格 / 題型比例 / 難度分佈 | `prompts/examiner.yaml`（純文字，不用動 Python） |
| 改評分標準 / 權重 | `prompts/judge.yaml` |
| 換 LLM 後端（Hermes / OpenAI / Claude API） | `nexus_client.py`（保留 `generate_response_sync` 簽章） |
| 加新角色（critic、fact-checker） | 新 YAML + 上游呼叫；不用動 prompt_loader |
| 改 HTML 報告樣式 | `templates/report.html`（自包含 Jinja2 模板） |
| 支援 OCR | `spec_loader.py::_read_pdf_file`（加 pytesseract fallback） |
| 題庫加欄位（例如 tags、category） | 只要加在 JSON 裡，`exam_runner` 讀 `questions` list 不檢查 schema |

**不建議從這裡進的**：

- 把 `exam_runner.py` 拆成 service class — 它是 CLI 腳本，保持平鋪 function 比較好讀。
- 把 prompt 搬進 Python `.py` — 那會破壞「非工程師也能改 prompt」的核心價值。

---

## 13. Git 與 Branch 習慣

- 目前單人專案、`main` 單分支、直接 push。交接後可以改用 PR flow。
- Commit message 格式：`<type>: <描述>`（type = `feat` / `fix` / `docs` / `refactor` / `test` / `chore`）。
- **被 codex 或 code-reviewer agent 審過的程式改動**，commit message 標 `[codex-reviewed]`；文件類改動可標 `[codex-review: skipped, reason=docs-only]`。
- `.gitignore` 目前只擋 `__pycache__/`、`*.pyc`、`.pytest_cache/`。其餘敏感檔（`config.yaml` 真 key、`results/` 裡的真答案）**請自己小心**不要 commit。

---

## 14. 給接手同事的起手式

**第一天先做這個順序：**

1. `git clone` → `pip install -r requirements.txt`
2. `python -m pytest tests/ -v` — 應該 30 passed
3. 看 `USER_GUIDE.md` 跑一次 end-to-end（用 `question_bank/example_5q.json` 就夠了）
4. 看本文件 §3 檔案責任矩陣，對照 `exam_runner.py::main` 追一次 `run_exam` 的資料流
5. 看 `spec_loader.py` + 對應測試（這塊最新，也最容易誤改）
6. 瀏覽 `prompts/*.yaml` — 這是系統的「行為定義」，要先了解而不是讀程式碼

**第一週可以挑的小任務（難度遞增）：**

- 改 `prompts/examiner.yaml`，把題型比例從 60/40 改成你想要的。跑 `--generate` 驗證。
- 加一題 `test_spec_loader.py` 的測試（例如「檔案大小上限」或「非法編碼」邊界）。
- 換題庫跑 `run_exam`，看 HTML 報告。嘗試改 `templates/report.html` 的樣式。

**要碰 `nexus_client.py` / `exam_runner.py` 主流程之前**，把本文件 §5 §6 §11 先讀完，避免踩到之前踩過的坑。

---

## 15. 快速聯絡

- 原作者：bill_chen（可以找前手問）
- Git remote：見 `git remote -v`
- 公司 LLM 平台：Nexus（內網 `http://ainexus.phison.com:5155`）
- 未來計畫：遷移到 Hermes agent + Qwen 3.5 系列

有問題先看 §11 的 debug tips；解不了再來問。
