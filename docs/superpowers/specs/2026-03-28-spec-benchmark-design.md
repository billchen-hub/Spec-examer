# Spec Benchmark Test System - Design Document

> Date: 2026-03-28
> Status: Approved

## Overview

一套針對 spec 文件的 AI 能力評測系統。讀取技術規格文件後自動出題，讓地端 AI（Nexus 平台）作答，再由另一個 AI 裁判打分，最終產出可攜帶的 HTML 報告和改善建議。

## Goals

1. 評估地端 AI 對 spec 文件的理解程度
2. 產出結構化的改善建議，可直接回饋給地端 AI 訓練
3. 追蹤多次考試的成績變化趨勢
4. 讓非技術人員也能雙擊 bat 執行考試

## Architecture

### 專案結構

```
spec-benchmark-test/
├── specs/                      ← 放 spec 檔案（PDF/MD/TXT/LOG）
├── prompts/                    ← 可編輯的 prompt 模板（YAML）
│   ├── examiner.yaml           ← 出題者 prompt
│   ├── examinee.yaml           ← 答題者 prompt
│   └── judge.yaml              ← 裁判 prompt
├── question_bank/              ← 題庫 JSON
├── results/                    ← 考試結果（HTML + JSON + suggestions.md）
├── templates/
│   └── report.html             ← HTML 報告模板
├── config.yaml                 ← 全域設定
├── requirements.txt            ← Python 相依套件
├── nexus_client.py             ← Nexus API 封裝（已有）
├── examiner.py                 ← 出題模組（Claude Code 呼叫）
├── exam_runner.py              ← 考試主流程 CLI
├── judge.py                    ← 裁判模組
├── report_generator.py         ← 產出報告
├── run_exam.bat                ← 傻瓜啟動考試
├── setup.bat                   ← 首次環境安裝
└── USER_GUIDE.md               ← 使用說明
```

### 模組職責

| 模組 | 職責 | 呼叫方式 |
|---|---|---|
| `examiner.py` | 讀 spec、產生題庫 JSON | Claude Code session 中執行 |
| `exam_runner.py` | CLI 主程式，串接答題→裁判→報告 | `python exam_runner.py` 或 `run_exam.bat` |
| `judge.py` | 呼叫 Nexus 裁判 API、解析評分 | exam_runner 內部呼叫 |
| `nexus_client.py` | Nexus REST API 封裝 | judge.py / exam_runner 呼叫 |
| `report_generator.py` | 產出 HTML + JSON + suggestions.md | exam_runner 內部呼叫 |

## Two Separate Flows

### Flow 1: Question Generation (出題)

在 Claude Code session 中執行，利用 Claude 訂閱而非 API 費用。

```
使用者在 Claude Code 中說「幫我出題」
  → Claude Code 讀 specs/ 資料夾，列出可用 spec
  → 使用者選一份
  → Claude Code 讀 spec 內容 + 讀 prompts/examiner.yaml
  → Claude Code 依 prompt 模板產生題目
  → 存入 question_bank/<spec名稱>_<題數>q.json
```

- 出題不需要每次都執行，題庫產出後可重複使用
- 題型：問答題（約 60%）+ 選擇題（約 40%，四選一）
- 難度分佈：30% 簡單、50% 中等、20% 困難
- 預設出 100 題，可在 prompts/examiner.yaml 中調整

### Flow 2: Exam Execution (考試)

獨立 Python CLI，只依賴 Nexus API，可在任何有 Python 的機器上跑。

```
run_exam.bat 雙擊啟動
  → 讀 config.yaml（題庫路徑、Nexus 認證、考試模式）
  → 讀題庫 JSON
  → 依模式選題（full 全考 / random 隨機抽取）
  → 逐題：
      1. 填入 prompts/examinee.yaml → 呼叫 Nexus 答題者 → 取得答案
      2. 填入 prompts/judge.yaml → 呼叫 Nexus 裁判 → 取得分數 + feedback
      3. 終端印出進度（第 N/100 題，目前平均 X 分）
  → 全部答完：
      4. 呼叫裁判做綜合建議
      5. 產出 HTML 報告 + JSON + suggestions.md
      6. 終端印出報告路徑
```

## Data Structures

### Question Bank (`question_bank/*.json`)

```json
{
  "metadata": {
    "spec_file": "api_spec_v2.pdf",
    "generated_at": "2026-03-28T14:30:00",
    "total_questions": 100
  },
  "questions": [
    {
      "id": 1,
      "type": "qa",
      "difficulty": "medium",
      "question": "當 API 收到無效的 token 時，應該回傳什麼 HTTP status code？請說明原因。",
      "reference_answer": "應回傳 401 Unauthorized。根據 spec 第 3.2 節...",
      "source_section": "3.2 Authentication"
    },
    {
      "id": 2,
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "根據 spec，API rate limit 的預設值是？",
      "options": ["A) 100 req/min", "B) 500 req/min", "C) 1000 req/min", "D) 無限制"],
      "correct_answer": "C",
      "explanation": "根據 spec 第 5.1 節，預設 rate limit 為 1000 req/min",
      "source_section": "5.1 Rate Limiting"
    }
  ]
}
```

### Exam Results (`results/*.json`)

```json
{
  "exam_id": "exam_20260328_143000",
  "timestamp": "2026-03-28T14:30:00",
  "config": {
    "question_bank": "api_spec_v2.json",
    "mode": "full",
    "total_questions": 100,
    "examinee_share_code": "xxx",
    "judge_share_code": "yyy"
  },
  "average_score": 72.5,
  "results": [
    {
      "question_id": 1,
      "question": "...",
      "reference_answer": "...",
      "examinee_answer": "...",
      "score": 85,
      "judge_feedback": "回答正確但缺少對 spec 第 3.2 節的直接引用...",
      "improvement_suggestion": "建議加入規則：回答認證相關問題時，必須引用 spec 的具體章節編號..."
    }
  ],
  "overall_suggestion": "整體建議：答題者在安全性相關題目表現較弱，建議在 system prompt 中加入..."
}
```

### Suggestions File (`results/*_suggestions.md`)

可直接複製貼上給地端 AI 的整合建議文件：

```markdown
# Spec Benchmark 改善建議
> 考試時間：2026-03-28 14:30 | 平均分數：72.5/100

## 各題改善建議

### 第 1 題（85 分）- Authentication Error Handling
建議加入規則：...

## 綜合改善建議（可直接作為 prompt/規則使用）

你是一個熟悉 [spec 名稱] 的技術助手。請遵守以下規則：
1. ...
2. ...
```

## Prompt Templates

三份 YAML 模板放在 `prompts/`，使用 `{{variable}}` 佔位符，程式執行時自動替換。使用者直接編輯 YAML 檔即可自訂 prompt，不需要改程式碼。

### `prompts/examiner.yaml`

```yaml
name: "出題者"
description: "根據 spec 文件產生題庫"
template: |
  你是一位專業的技術規格考試出題者。

  請根據以下 spec 文件內容，出 {{num_questions}} 題考題。
  題型分配：約 60% 問答題、40% 選擇題（四選一）。

  出題原則：
  - 題目必須能從 spec 中找到明確答案
  - 涵蓋 spec 的各個章節，不要集中在某一段
  - 難度分佈：30% 簡單、50% 中等、20% 困難
  - 每題標註出處章節
  - 問答題須附完整參考答案
  - 選擇題須附正確選項及解釋

  請以下列 JSON 格式輸出：
  {{output_format}}
```

### `prompts/examinee.yaml`

```yaml
name: "答題者"
description: "根據知識回答考題"
template: |
  你是一位技術人員，正在接受關於技術規格文件的測驗。

  請根據你的知識，回答以下考題。

  作答原則：
  - 盡可能引用具體的規格章節或條文
  - 回答要完整且精確
  - 選擇題請先選出答案，再說明理由
  - 如果不確定，請說明你的推理過程

  考題：
  {{question}}
```

### `prompts/judge.yaml`

```yaml
name: "裁判"
description: "評分並提供改善建議"
template: |
  你是一位嚴格但公正的技術規格測驗裁判。

  ## 評分任務
  請比對「參考答案」與「受測者答案」，給予 0-100 分。

  ## 評分標準
  - 正確性（50%）：答案是否與 spec 一致
  - 完整性（30%）：是否涵蓋所有關鍵點
  - 精確性（20%）：是否有多餘或錯誤的資訊

  ## 題目
  {{question}}

  ## 參考答案
  {{reference_answer}}

  ## 受測者答案
  {{examinee_answer}}

  ## 請以下列 JSON 格式回覆
  {
    "score": <0-100>,
    "feedback": "<評語，說明扣分原因>",
    "improvement_suggestion": "<如果下次要答對，應該在 prompt 或規則中加入什麼>"
  }
```

## Configuration (`config.yaml`)

```yaml
nexus:
  base_url: "http://ainexus.phison.com:5155"

credentials:
  examinee:
    user_key: "填入你的 key"
    share_code: "填入答題者 share_code"
  judge:
    user_key: "填入你的 key"
    share_code: "填入裁判 share_code"

exam:
  question_bank: "question_bank/api_spec_v2.json"
  default_mode: "full"
  default_random_count: 20
  default_question_count: 100

paths:
  specs_dir: "specs/"
  question_bank_dir: "question_bank/"
  results_dir: "results/"
  prompts_dir: "prompts/"
```

## HTML Report UI

### Layout

```
┌──────────────────────────────────────────────────────┐
│  Spec Benchmark 報告  |  2026-03-28  |  平均：72.5分  │
├────────────┬─────────────────────────────────────────┤
│            │  第 3 題（問答題）            85/100     │
│  #1  85分  │─────────────────────────────────────────│
│  #2  60分  │  【題目】                               │
│ >#3  85分  │  當 API 收到無效 token 時...            │
│  #4  90分  │                                         │
│  #5  45分  │  【標準答案】                           │
│  #6  70分  │  應回傳 401 Unauthorized...             │
│  ...       │                                         │
│            │  【答題者回答】                          │
│            │  回傳 401 錯誤碼...                     │
│            │                                         │
│ ─────────  │  【裁判評語】                           │
│ 平均: 72.5 │  回答正確但缺少章節引用...              │
│ 最高: 95   │                                         │
│ 最低: 30   │  【改善建議】                           │
│            │  建議在 prompt 中加入...                 │
├────────────┴─────────────────────────────────────────┤
│  【綜合改善建議】                                     │
│  整體而言，答題者在安全性章節表現較弱...               │
└──────────────────────────────────────────────────────┘
```

### Features

- **Left panel**: Question list with score per item. Color coded: green (>=80), yellow (60-79), red (<60). Click to switch right panel content.
- **Left panel bottom**: Stats summary (average, highest, lowest, pass rate).
- **Right panel**: Question, reference answer, examinee answer, judge feedback, improvement suggestion.
- **Bottom**: Overall improvement suggestion.
- **Self-contained**: All CSS/JS inline in a single HTML file. Double-click to open on any machine.

## Entry Points

### For Question Generation (出題)

In Claude Code session:
```
使用者：「幫我出題」
Claude Code 執行 examiner.py 流程
```

### For Exam Execution (考試)

1. First time: double-click `setup.bat` to install dependencies
2. Edit `config.yaml` with Nexus credentials and question bank path
3. Double-click `run_exam.bat` to start exam

### CLI Options (advanced)

```bash
# Override config with CLI args
python exam_runner.py --mode random --count 30
python exam_runner.py --bank question_bank/other_spec.json
```

## Technology Stack

- **Language**: Python 3.10+
- **Dependencies**: requests, pyyaml, jinja2 (for HTML template)
- **Nexus API**: REST, custom format (existing nexus_client.py)
- **Question Generation**: Claude Code (subscription, no API cost)
- **Report**: Self-contained static HTML with inline CSS/JS
- **Config**: YAML files for settings and prompt templates
