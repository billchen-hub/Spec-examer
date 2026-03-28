# Spec Benchmark Test System - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-based AI benchmark system that generates questions from spec documents, has a local AI answer them via Nexus API, judges answers, and produces self-contained HTML reports with improvement suggestions.

**Architecture:** Two independent flows share a common question bank JSON. Flow 1 (question generation) runs inside Claude Code reading local spec files. Flow 2 (exam execution) is a standalone Python CLI calling Nexus REST API for both answering and judging, producing HTML + JSON + Markdown reports.

**Tech Stack:** Python 3.10+, requests, PyYAML, Jinja2, vanilla HTML/CSS/JS

---

## File Structure

```
spec-benchmark-test/
├── specs/                          ← User puts spec files here
├── prompts/
│   ├── examiner.yaml               ← Question generator prompt template
│   ├── examinee.yaml               ← Answer provider prompt template
│   └── judge.yaml                  ← Scorer prompt template
├── question_bank/                  ← Generated question bank JSONs
├── results/                        ← Exam results (HTML + JSON + suggestions.md)
├── templates/
│   └── report.html                 ← Jinja2 HTML report template
├── tests/
│   ├── test_prompt_loader.py
│   ├── test_exam_runner.py
│   └── test_report_generator.py
├── config.yaml                     ← Global settings
├── requirements.txt                ← Python dependencies
├── nexus_client.py                 ← Nexus API wrapper (existing)
├── prompt_loader.py                ← YAML prompt loading + variable substitution
├── examiner.py                     ← Question generation helper (Claude Code)
├── exam_runner.py                  ← Main exam CLI
├── judge.py                        ← Judging module
├── report_generator.py             ← HTML/JSON/suggestions output
├── run_exam.bat                    ← One-click exam launcher
├── setup.bat                       ← First-time environment setup
├── USER_GUIDE.md                   ← Usage instructions
└── skills/spec-benchmark/SKILL.md  ← Reusable architecture skill (already created)
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `config.yaml`, `requirements.txt`, `prompts/examiner.yaml`, `prompts/examinee.yaml`, `prompts/judge.yaml`
- Create directories: `specs/`, `question_bank/`, `results/`, `templates/`, `tests/`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p specs question_bank results templates tests prompts
```

- [ ] **Step 2: Create requirements.txt**

```
requests>=2.31.0
PyYAML>=6.0.1
Jinja2>=3.1.2
```

- [ ] **Step 3: Create config.yaml**

```yaml
nexus:
  base_url: "http://ainexus.phison.com:5155"

credentials:
  examinee:
    user_key: "YOUR_EXAMINEE_USER_KEY"
    share_code: "YOUR_EXAMINEE_SHARE_CODE"
  judge:
    user_key: "YOUR_JUDGE_USER_KEY"
    share_code: "YOUR_JUDGE_SHARE_CODE"

exam:
  question_bank: "question_bank/example.json"
  default_mode: "full"
  default_random_count: 20
  default_question_count: 100

paths:
  specs_dir: "specs/"
  question_bank_dir: "question_bank/"
  results_dir: "results/"
  prompts_dir: "prompts/"
```

- [ ] **Step 4: Create prompts/examiner.yaml**

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

  請嚴格以下列 JSON 格式輸出（不要加 markdown code fence）：
  {
    "questions": [
      {
        "id": 1,
        "type": "qa",
        "difficulty": "easy|medium|hard",
        "question": "題目內容",
        "reference_answer": "完整參考答案",
        "source_section": "出處章節"
      },
      {
        "id": 2,
        "type": "multiple_choice",
        "difficulty": "easy|medium|hard",
        "question": "題目內容",
        "options": ["A) 選項一", "B) 選項二", "C) 選項三", "D) 選項四"],
        "correct_answer": "C",
        "explanation": "解釋為何正確",
        "source_section": "出處章節"
      }
    ]
  }
```

- [ ] **Step 5: Create prompts/examinee.yaml**

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

- [ ] **Step 6: Create prompts/judge.yaml**

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

  ## 題目類型
  {{question_type}}

  ## 題目
  {{question}}

  ## 參考答案
  {{reference_answer}}

  ## 受測者答案
  {{examinee_answer}}

  ## 請嚴格以下列 JSON 格式回覆（不要加 markdown code fence）：
  {
    "score": 75,
    "feedback": "評語，說明扣分原因",
    "improvement_suggestion": "如果下次要答對，應該在 prompt 或規則中加入什麼"
  }

overall_template: |
  你是一位嚴格但公正的技術規格測驗裁判。

  以下是一份考試的所有題目與評分結果摘要：

  {{results_summary}}

  平均分數：{{average_score}} 分

  請根據以上結果，撰寫一份綜合改善建議。

  要求：
  - 分析答題者的弱點領域（哪些主題/章節表現差）
  - 分析答題者的強項領域
  - 提供具體、可執行的改善建議
  - 最後產出一段可以直接作為 system prompt 或規則使用的文字，讓答題者下次表現更好

  請以純文字回覆，不要用 JSON 格式。
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 8: Commit**

```bash
git init
git add config.yaml requirements.txt prompts/ specs/ question_bank/ results/ templates/ tests/
git commit -m "chore: project scaffolding with config and prompt templates"
```

---

### Task 2: Prompt Loader Module

**Files:**
- Create: `prompt_loader.py`
- Test: `tests/test_prompt_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_prompt_loader.py`:

```python
import os
import pytest
import tempfile
import yaml

from prompt_loader import PromptLoader


def make_yaml(tmp_path, filename, data):
    path = os.path.join(tmp_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


class TestPromptLoader:
    def test_load_prompt_file(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        result = loader.load("test")
        assert result["name"] == "test"
        assert "{{name}}" in result["template"]

    def test_render_with_variables(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("test", {"name": "Alice", "role": "judge"})
        assert rendered == "Hello Alice, you are judge."

    def test_render_missing_variable_left_as_is(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("test", {"name": "Alice"})
        assert rendered == "Hello Alice, you are {{role}}."

    def test_load_nonexistent_raises(self, tmp_path):
        loader = PromptLoader(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_render_named_template(self, tmp_path):
        data = {
            "name": "judge",
            "template": "Score: {{score}}",
            "overall_template": "Summary: {{summary}}"
        }
        make_yaml(tmp_path, "judge.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("judge", {"summary": "Good"}, template_key="overall_template")
        assert rendered == "Summary: Good"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "C:/Users/ASUS/Desktop/claude project/spec benchmark test"
python -m pytest tests/test_prompt_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_loader'`

- [ ] **Step 3: Implement prompt_loader.py**

Create `prompt_loader.py`:

```python
import os
import re
import yaml
from typing import Dict, Optional


class PromptLoader:
    """Loads YAML prompt templates and renders them with variable substitution."""

    def __init__(self, prompts_dir: str):
        self.prompts_dir = prompts_dir

    def load(self, name: str) -> Dict:
        """Load a prompt YAML file by name (without .yaml extension)."""
        path = os.path.join(self.prompts_dir, f"{name}.yaml")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def render(self, name: str, variables: Dict[str, str], template_key: str = "template") -> str:
        """Load a prompt and substitute {{variable}} placeholders."""
        data = self.load(name)
        template = data.get(template_key, "")
        return self._substitute(template, variables)

    def _substitute(self, template: str, variables: Dict[str, str]) -> str:
        """Replace {{key}} with value. Leave unmatched placeholders as-is."""
        def replacer(match):
            key = match.group(1).strip()
            return str(variables.get(key, match.group(0)))
        return re.sub(r"\{\{(\s*\w+\s*)\}\}", replacer, template)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompt_loader.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_loader.py tests/test_prompt_loader.py
git commit -m "feat: prompt loader with YAML template rendering"
```

---

### Task 3: Adapt Nexus Client

**Files:**
- Modify: `nexus_client.py`

The existing client uses `async def` with synchronous `requests`. Adapt it to support synchronous calls since `exam_runner.py` is a standard CLI script.

- [ ] **Step 1: Add synchronous methods to nexus_client.py**

Add a `generate_response_sync` and `upload_file_sync` method below the existing async ones. Keep the async originals intact so the user's other projects are not broken.

Add these methods to the `NexusClient` class:

```python
def generate_response_sync(self, share_code: str, history: List[Dict], system_prompt: str = None, files: List[Dict] = []) -> str:
    """Synchronous version of generate_response."""
    try:
        url = f"{self.base_url}/api/external/v1/callAgent/json"
        messages = [{"role": 0, "message": system_prompt}] if system_prompt else []

        for msg in history:
            messages.append({
                "role": msg["role"],
                "message": msg["content"]
            })

        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        payload = {
            'shareCode': share_code,
            'prompt': "<<<" + messages[-1]['message'] + ">>>",
            'previousMessage': messages[:-1],
            'files': files
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        response_data = response.json()
        logger.info(f"API Response: {json.dumps(response_data, indent=2, ensure_ascii=False)[:500]}")

        return response_data['content']
    except requests.exceptions.Timeout:
        logger.error("Nexus API timeout")
        return "[ERROR] Nexus API 請求逾時，請稍後再試。"
    except requests.exceptions.RequestException as e:
        logger.error(f"Post request error: {e}")
        return f"[ERROR] Nexus API 請求錯誤: {e}"
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        return f"[ERROR] LLM 產生回應時出錯: {e}"
```

- [ ] **Step 2: Commit**

```bash
git add nexus_client.py
git commit -m "feat: add sync methods to NexusClient for CLI usage"
```

---

### Task 4: Judge Module

**Files:**
- Create: `judge.py`

- [ ] **Step 1: Create judge.py**

```python
import json
import logging
import re
from typing import Dict, List

from nexus_client import NexusClient
from prompt_loader import PromptLoader

logger = logging.getLogger("[Judge]")


class Judge:
    """Calls Nexus judge API to score examinee answers."""

    def __init__(self, nexus_client: NexusClient, share_code: str, prompt_loader: PromptLoader):
        self.client = nexus_client
        self.share_code = share_code
        self.prompt_loader = prompt_loader

    def score_answer(self, question: Dict, examinee_answer: str) -> Dict:
        """Score a single answer. Returns dict with score, feedback, improvement_suggestion."""
        q_type = question.get("type", "qa")
        if q_type == "multiple_choice":
            ref_answer = f"正確答案：{question.get('correct_answer', '')}\n解釋：{question.get('explanation', '')}"
            question_text = question["question"] + "\n" + "\n".join(question.get("options", []))
        else:
            ref_answer = question.get("reference_answer", "")
            question_text = question["question"]

        prompt = self.prompt_loader.render("judge", {
            "question_type": "選擇題" if q_type == "multiple_choice" else "問答題",
            "question": question_text,
            "reference_answer": ref_answer,
            "examinee_answer": examinee_answer,
        })

        history = [{"role": 1, "content": prompt}]
        response = self.client.generate_response_sync(self.share_code, history)

        return self._parse_response(response)

    def generate_overall_suggestion(self, results: List[Dict], average_score: float) -> str:
        """Generate overall improvement suggestion from all results."""
        summary_lines = []
        for r in results:
            summary_lines.append(
                f"第 {r['question_id']} 題（{r['score']} 分）：{r.get('judge_feedback', '')[:100]}"
            )
        results_summary = "\n".join(summary_lines)

        prompt = self.prompt_loader.render("judge", {
            "results_summary": results_summary,
            "average_score": str(average_score),
        }, template_key="overall_template")

        history = [{"role": 1, "content": prompt}]
        return self.client.generate_response_sync(self.share_code, history)

    def _parse_response(self, response: str) -> Dict:
        """Parse judge JSON response. Fallback to defaults if parsing fails."""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "score": max(0, min(100, int(data.get("score", 0)))),
                    "feedback": data.get("feedback", ""),
                    "improvement_suggestion": data.get("improvement_suggestion", ""),
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse judge response as JSON: {e}")

        # Fallback: return the raw response as feedback with score 0
        return {
            "score": 0,
            "feedback": f"[裁判回應無法解析] {response[:500]}",
            "improvement_suggestion": "",
        }
```

- [ ] **Step 2: Commit**

```bash
git add judge.py
git commit -m "feat: judge module for scoring and overall suggestions"
```

---

### Task 5: Report Generator

**Files:**
- Create: `report_generator.py`, `templates/report.html`
- Test: `tests/test_report_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_report_generator.py`:

```python
import json
import os
import pytest

from report_generator import ReportGenerator


def make_sample_results():
    return {
        "exam_id": "exam_20260328_140000",
        "timestamp": "2026-03-28T14:00:00",
        "config": {
            "question_bank": "test.json",
            "mode": "full",
            "total_questions": 2,
        },
        "average_score": 72.5,
        "results": [
            {
                "question_id": 1,
                "type": "qa",
                "question": "What is X?",
                "reference_answer": "X is Y.",
                "examinee_answer": "X is probably Y.",
                "score": 85,
                "judge_feedback": "Mostly correct.",
                "improvement_suggestion": "Be more precise.",
            },
            {
                "question_id": 2,
                "type": "multiple_choice",
                "question": "Which is correct?",
                "options": ["A) One", "B) Two", "C) Three", "D) Four"],
                "reference_answer": "正確答案：B\n解釋：Two is correct.",
                "examinee_answer": "A",
                "score": 60,
                "judge_feedback": "Wrong answer.",
                "improvement_suggestion": "Review section 2.",
            },
        ],
        "overall_suggestion": "Focus on section 2.",
    }


class TestReportGenerator:
    def test_save_json(self, tmp_path):
        data = make_sample_results()
        gen = ReportGenerator(str(tmp_path), template_dir=None)
        gen.save_json(data)
        json_path = os.path.join(tmp_path, f"{data['exam_id']}.json")
        assert os.path.exists(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["average_score"] == 72.5
        assert len(loaded["results"]) == 2

    def test_save_suggestions(self, tmp_path):
        data = make_sample_results()
        gen = ReportGenerator(str(tmp_path), template_dir=None)
        gen.save_suggestions(data)
        md_path = os.path.join(tmp_path, f"{data['exam_id']}_suggestions.md")
        assert os.path.exists(md_path)
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "72.5" in content
        assert "第 1 題" in content
        assert "Focus on section 2" in content

    def test_save_html(self, tmp_path):
        data = make_sample_results()
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        gen = ReportGenerator(str(tmp_path), template_dir=template_dir)
        gen.save_html(data)
        html_path = os.path.join(tmp_path, f"{data['exam_id']}.html")
        assert os.path.exists(html_path)
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "72.5" in content
        assert "What is X?" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_report_generator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'report_generator'`

- [ ] **Step 3: Create templates/report.html**

Create the self-contained HTML report template. This is a Jinja2 template that embeds data as JSON and uses vanilla JS for interactivity.

Create `templates/report.html`:

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Spec Benchmark 報告 - {{ exam_id }}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif; background: #f0f2f5; color: #333; }

  .header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #fff; padding: 20px 30px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .header h1 { font-size: 1.4em; }
  .header .meta { font-size: 0.95em; opacity: 0.85; }
  .header .avg-score {
    font-size: 2em; font-weight: bold;
    padding: 8px 20px; border-radius: 12px;
  }
  .avg-green { background: rgba(46,204,113,0.25); color: #2ecc71; }
  .avg-yellow { background: rgba(241,196,15,0.25); color: #f1c40f; }
  .avg-red { background: rgba(231,76,60,0.25); color: #e74c3c; }

  .container { display: flex; height: calc(100vh - 80px); }

  /* Left Panel */
  .left-panel {
    width: 240px; min-width: 240px;
    background: #fff; border-right: 1px solid #e0e0e0;
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .question-list {
    flex: 1; overflow-y: auto; padding: 8px;
  }
  .q-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 12px; margin-bottom: 4px;
    border-radius: 8px; cursor: pointer;
    transition: background 0.15s;
    font-size: 0.9em;
  }
  .q-item:hover { background: #f5f5f5; }
  .q-item.active { background: #e8f0fe; font-weight: 600; }
  .q-item .q-label { color: #555; }
  .q-score {
    font-weight: 700; padding: 2px 8px;
    border-radius: 6px; font-size: 0.85em;
  }
  .score-green { background: #d5f5e3; color: #27ae60; }
  .score-yellow { background: #fef9e7; color: #f39c12; }
  .score-red { background: #fadbd8; color: #c0392b; }

  .stats-box {
    border-top: 1px solid #e0e0e0; padding: 14px;
    font-size: 0.85em; background: #fafafa;
  }
  .stats-box .stat-row {
    display: flex; justify-content: space-between;
    margin-bottom: 4px;
  }
  .stats-box .stat-label { color: #888; }
  .stats-box .stat-value { font-weight: 600; }

  /* Right Panel */
  .right-panel {
    flex: 1; overflow-y: auto; padding: 24px 32px;
  }
  .detail-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px; padding-bottom: 12px;
    border-bottom: 2px solid #e0e0e0;
  }
  .detail-header h2 { font-size: 1.2em; }
  .detail-score { font-size: 1.8em; font-weight: 700; }

  .section { margin-bottom: 24px; }
  .section-title {
    font-size: 0.85em; font-weight: 700;
    color: #888; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 8px;
    padding-left: 2px;
  }
  .section-content {
    background: #fff; border-radius: 10px;
    padding: 16px 20px; border: 1px solid #e8e8e8;
    line-height: 1.7; white-space: pre-wrap;
    font-size: 0.95em;
  }
  .section-content.answer { border-left: 4px solid #3498db; }
  .section-content.reference { border-left: 4px solid #2ecc71; }
  .section-content.feedback { border-left: 4px solid #f39c12; }
  .section-content.suggestion { border-left: 4px solid #9b59b6; }

  /* Bottom Overall */
  .overall-panel {
    background: #fff; border-top: 2px solid #e0e0e0;
    padding: 20px 32px; margin-left: 240px;
  }
  .overall-panel .section-title { font-size: 1em; color: #1a1a2e; }
  .overall-panel .section-content {
    border-left: 4px solid #1a1a2e;
    max-height: 300px; overflow-y: auto;
  }

  .badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 12px; font-size: 0.8em; font-weight: 600;
    margin-left: 8px;
  }
  .badge-qa { background: #ebf5fb; color: #2e86c1; }
  .badge-mc { background: #f5eef8; color: #7d3c98; }
  .badge-easy { background: #d5f5e3; color: #27ae60; }
  .badge-medium { background: #fef9e7; color: #f39c12; }
  .badge-hard { background: #fadbd8; color: #c0392b; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Spec Benchmark 報告</h1>
    <div class="meta">{{ timestamp }} | {{ config.question_bank }} | {{ config.mode }} 模式 ({{ config.total_questions }} 題)</div>
  </div>
  <div class="avg-score {% if average_score >= 80 %}avg-green{% elif average_score >= 60 %}avg-yellow{% else %}avg-red{% endif %}">
    {{ "%.1f"|format(average_score) }} 分
  </div>
</div>

<div class="container">
  <div class="left-panel">
    <div class="question-list" id="questionList">
      {% for r in results %}
      <div class="q-item {% if loop.first %}active{% endif %}" onclick="showQuestion({{ loop.index0 }})" id="q-{{ loop.index0 }}">
        <span class="q-label">#{{ r.question_id }}</span>
        <span class="q-score {% if r.score >= 80 %}score-green{% elif r.score >= 60 %}score-yellow{% else %}score-red{% endif %}">
          {{ r.score }} 分
        </span>
      </div>
      {% endfor %}
    </div>
    <div class="stats-box">
      <div class="stat-row"><span class="stat-label">平均</span><span class="stat-value">{{ "%.1f"|format(average_score) }}</span></div>
      <div class="stat-row"><span class="stat-label">最高</span><span class="stat-value">{{ max_score }}</span></div>
      <div class="stat-row"><span class="stat-label">最低</span><span class="stat-value">{{ min_score }}</span></div>
      <div class="stat-row"><span class="stat-label">及格率</span><span class="stat-value">{{ "%.0f"|format(pass_rate) }}%</span></div>
    </div>
  </div>

  <div class="right-panel" id="rightPanel">
    <!-- Filled by JS -->
  </div>
</div>

<div class="overall-panel">
  <div class="section-title">綜合改善建議</div>
  <div class="section-content suggestion">{{ overall_suggestion }}</div>
</div>

<script>
const DATA = {{ results_json }};

function showQuestion(idx) {
  document.querySelectorAll('.q-item').forEach(el => el.classList.remove('active'));
  document.getElementById('q-' + idx).classList.add('active');

  const r = DATA[idx];
  const typeLabel = r.type === 'multiple_choice' ? '選擇題' : '問答題';
  const typeBadge = r.type === 'multiple_choice' ? 'badge-mc' : 'badge-qa';
  const diffBadge = 'badge-' + (r.difficulty || 'medium');
  const diffLabel = {'easy':'簡單','medium':'中等','hard':'困難'}[r.difficulty||'medium'];

  const scoreClass = r.score >= 80 ? 'score-green' : (r.score >= 60 ? 'score-yellow' : 'score-red');

  let questionText = r.question;
  if (r.options) {
    questionText += '\n\n' + r.options.join('\n');
  }

  document.getElementById('rightPanel').innerHTML = `
    <div class="detail-header">
      <h2>第 ${r.question_id} 題
        <span class="badge ${typeBadge}">${typeLabel}</span>
        <span class="badge ${diffBadge}">${diffLabel}</span>
      </h2>
      <span class="detail-score ${scoreClass}">${r.score}/100</span>
    </div>
    <div class="section">
      <div class="section-title">題目</div>
      <div class="section-content">${escHtml(questionText)}</div>
    </div>
    <div class="section">
      <div class="section-title">標準答案</div>
      <div class="section-content reference">${escHtml(r.reference_answer)}</div>
    </div>
    <div class="section">
      <div class="section-title">答題者回答</div>
      <div class="section-content answer">${escHtml(r.examinee_answer)}</div>
    </div>
    <div class="section">
      <div class="section-title">裁判評語</div>
      <div class="section-content feedback">${escHtml(r.judge_feedback)}</div>
    </div>
    <div class="section">
      <div class="section-title">改善建議</div>
      <div class="section-content suggestion">${escHtml(r.improvement_suggestion)}</div>
    </div>
  `;
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
}

// Show first question on load
showQuestion(0);
</script>
</body>
</html>
```

- [ ] **Step 4: Implement report_generator.py**

Create `report_generator.py`:

```python
import json
import os
import logging
from datetime import datetime
from typing import Dict

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("[ReportGenerator]")


class ReportGenerator:
    """Generates HTML, JSON, and Markdown suggestion reports."""

    def __init__(self, results_dir: str, template_dir: str = None):
        self.results_dir = results_dir
        self.template_dir = template_dir
        os.makedirs(results_dir, exist_ok=True)

    def generate_all(self, data: Dict):
        """Generate all three output files: JSON, HTML, suggestions.md."""
        self.save_json(data)
        self.save_html(data)
        self.save_suggestions(data)
        exam_id = data["exam_id"]
        logger.info(f"Reports saved to {self.results_dir}/{exam_id}.*")

    def save_json(self, data: Dict):
        """Save structured JSON results."""
        path = os.path.join(self.results_dir, f"{data['exam_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_html(self, data: Dict):
        """Render and save self-contained HTML report."""
        if not self.template_dir:
            logger.warning("No template_dir set, skipping HTML generation.")
            return

        scores = [r["score"] for r in data["results"]]
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        pass_count = sum(1 for s in scores if s >= 60)
        pass_rate = (pass_count / len(scores) * 100) if scores else 0

        # Prepare results JSON for embedding in HTML
        results_for_js = []
        for r in data["results"]:
            results_for_js.append({
                "question_id": r["question_id"],
                "type": r.get("type", "qa"),
                "difficulty": r.get("difficulty", "medium"),
                "question": r["question"],
                "options": r.get("options"),
                "reference_answer": r["reference_answer"],
                "examinee_answer": r["examinee_answer"],
                "score": r["score"],
                "judge_feedback": r.get("judge_feedback", ""),
                "improvement_suggestion": r.get("improvement_suggestion", ""),
            })

        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template("report.html")

        html = template.render(
            exam_id=data["exam_id"],
            timestamp=data["timestamp"],
            config=data["config"],
            average_score=data["average_score"],
            results=data["results"],
            overall_suggestion=data.get("overall_suggestion", ""),
            max_score=max_score,
            min_score=min_score,
            pass_rate=pass_rate,
            results_json=json.dumps(results_for_js, ensure_ascii=False),
        )

        path = os.path.join(self.results_dir, f"{data['exam_id']}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def save_suggestions(self, data: Dict):
        """Save copy-pasteable improvement suggestions as Markdown."""
        lines = []
        lines.append(f"# Spec Benchmark 改善建議")
        lines.append(f"> 考試時間：{data['timestamp']} | 平均分數：{data['average_score']}/100")
        lines.append("")
        lines.append("## 各題改善建議")
        lines.append("")

        for r in data["results"]:
            suggestion = r.get("improvement_suggestion", "無")
            feedback = r.get("judge_feedback", "")
            lines.append(f"### 第 {r['question_id']} 題（{r['score']} 分）")
            lines.append(f"**題目：** {r['question'][:100]}...")
            lines.append(f"**評語：** {feedback}")
            lines.append(f"**建議：** {suggestion}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 綜合改善建議（可直接作為 prompt / 規則使用）")
        lines.append("")
        lines.append(data.get("overall_suggestion", "無"))

        path = os.path.join(self.results_dir, f"{data['exam_id']}_suggestions.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_report_generator.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add report_generator.py templates/report.html tests/test_report_generator.py
git commit -m "feat: report generator with HTML, JSON, and suggestions output"
```

---

### Task 6: Exam Runner (Main CLI)

**Files:**
- Create: `exam_runner.py`
- Test: `tests/test_exam_runner.py`

- [ ] **Step 1: Write failing test for config loading and question selection**

Create `tests/test_exam_runner.py`:

```python
import json
import os
import pytest

from exam_runner import load_config, select_questions


def make_question_bank(tmp_path, num=5):
    bank = {
        "metadata": {"spec_file": "test.pdf", "generated_at": "2026-03-28", "total_questions": num},
        "questions": [
            {"id": i + 1, "type": "qa", "difficulty": "medium",
             "question": f"Question {i+1}?", "reference_answer": f"Answer {i+1}",
             "source_section": f"Section {i+1}"}
            for i in range(num)
        ]
    }
    path = os.path.join(tmp_path, "test_bank.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f)
    return path


class TestSelectQuestions:
    def test_full_mode_returns_all(self, tmp_path):
        path = make_question_bank(tmp_path, 10)
        with open(path, "r") as f:
            bank = json.load(f)
        selected = select_questions(bank["questions"], "full", 5)
        assert len(selected) == 10

    def test_random_mode_returns_count(self, tmp_path):
        path = make_question_bank(tmp_path, 10)
        with open(path, "r") as f:
            bank = json.load(f)
        selected = select_questions(bank["questions"], "random", 3)
        assert len(selected) == 3

    def test_random_mode_count_exceeds_total(self, tmp_path):
        path = make_question_bank(tmp_path, 3)
        with open(path, "r") as f:
            bank = json.load(f)
        selected = select_questions(bank["questions"], "random", 10)
        assert len(selected) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_exam_runner.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement exam_runner.py**

Create `exam_runner.py`:

```python
import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime
from typing import Dict, List

import yaml

from nexus_client import NexusClient
from prompt_loader import PromptLoader
from judge import Judge
from report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("[ExamRunner]")

# ─── Config ────────────────────────────────────────────────
def load_config(config_path: str = "config.yaml") -> Dict:
    """Load config.yaml and return as dict."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── Question Selection ────────────────────────────────────
def select_questions(questions: List[Dict], mode: str, random_count: int) -> List[Dict]:
    """Select questions based on mode: 'full' returns all, 'random' samples random_count."""
    if mode == "random":
        count = min(random_count, len(questions))
        return random.sample(questions, count)
    return list(questions)


# ─── Main Exam Flow ────────────────────────────────────────
def run_exam(config: Dict, mode_override: str = None, count_override: int = None, bank_override: str = None):
    """Execute the full exam: load questions → answer → judge → report."""

    # Setup
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, config["paths"]["prompts_dir"])
    results_dir = os.path.join(base_dir, config["paths"]["results_dir"])
    templates_dir = os.path.join(base_dir, "templates")

    bank_path = bank_override or config["exam"]["question_bank"]
    if not os.path.isabs(bank_path):
        bank_path = os.path.join(base_dir, bank_path)

    mode = mode_override or config["exam"]["default_mode"]
    random_count = count_override or config["exam"]["default_random_count"]

    # Load question bank
    logger.info(f"載入題庫：{bank_path}")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    questions = select_questions(bank["questions"], mode, random_count)
    total = len(questions)
    logger.info(f"考試模式：{mode} | 題數：{total}")

    # Init clients
    prompt_loader = PromptLoader(prompts_dir)

    examinee_client = NexusClient(config["credentials"]["examinee"]["user_key"])
    examinee_share_code = config["credentials"]["examinee"]["share_code"]

    judge_client = NexusClient(config["credentials"]["judge"]["user_key"])
    judge_share_code = config["credentials"]["judge"]["share_code"]
    judge = Judge(judge_client, judge_share_code, prompt_loader)

    # Run exam
    now = datetime.now()
    exam_id = f"exam_{now.strftime('%Y%m%d_%H%M%S')}"
    results = []
    score_sum = 0

    for i, q in enumerate(questions):
        q_num = i + 1
        q_type = q.get("type", "qa")

        # Format question for examinee
        if q_type == "multiple_choice":
            question_text = q["question"] + "\n" + "\n".join(q.get("options", []))
        else:
            question_text = q["question"]

        # Examinee answers
        examinee_prompt = prompt_loader.render("examinee", {"question": question_text})
        history = [{"role": 1, "content": examinee_prompt}]
        print(f"\r  [{q_num}/{total}] 答題中...", end="", flush=True)
        examinee_answer = examinee_client.generate_response_sync(examinee_share_code, history)

        # Judge scores
        print(f"\r  [{q_num}/{total}] 評分中...", end="", flush=True)
        judge_result = judge.score_answer(q, examinee_answer)

        score = judge_result["score"]
        score_sum += score
        avg_so_far = score_sum / q_num

        result_entry = {
            "question_id": q["id"],
            "type": q_type,
            "difficulty": q.get("difficulty", "medium"),
            "question": q["question"],
            "options": q.get("options"),
            "reference_answer": q.get("reference_answer") or f"{q.get('correct_answer','')} - {q.get('explanation','')}",
            "examinee_answer": examinee_answer,
            "score": score,
            "judge_feedback": judge_result["feedback"],
            "improvement_suggestion": judge_result["improvement_suggestion"],
        }
        results.append(result_entry)

        status_icon = "✓" if score >= 60 else "✗"
        print(f"\r  [{q_num}/{total}] {status_icon} {score}分 (目前平均：{avg_so_far:.1f})")

    # Overall suggestion
    average_score = score_sum / total if total > 0 else 0
    print(f"\n  全部作答完畢！平均分數：{average_score:.1f}")
    print("  正在產生綜合建議...")

    overall_suggestion = judge.generate_overall_suggestion(results, average_score)

    # Build final data
    exam_data = {
        "exam_id": exam_id,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "question_bank": os.path.basename(bank_path),
            "mode": mode,
            "total_questions": total,
            "examinee_share_code": examinee_share_code,
            "judge_share_code": judge_share_code,
        },
        "average_score": round(average_score, 1),
        "results": results,
        "overall_suggestion": overall_suggestion,
    }

    # Generate reports
    report_gen = ReportGenerator(results_dir, templates_dir)
    report_gen.generate_all(exam_data)

    print(f"\n  報告已產出：")
    print(f"    HTML:  {results_dir}/{exam_id}.html")
    print(f"    JSON:  {results_dir}/{exam_id}.json")
    print(f"    建議:  {results_dir}/{exam_id}_suggestions.md")

    return exam_data


# ─── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Spec Benchmark 考試系統")
    parser.add_argument("--config", default="config.yaml", help="設定檔路徑")
    parser.add_argument("--mode", choices=["full", "random"], help="考試模式 (覆蓋 config)")
    parser.add_argument("--count", type=int, help="隨機抽題數 (覆蓋 config)")
    parser.add_argument("--bank", help="題庫檔案路徑 (覆蓋 config)")
    args = parser.parse_args()

    print("=" * 50)
    print("  Spec Benchmark 考試系統")
    print("=" * 50)

    config = load_config(args.config)
    run_exam(config, mode_override=args.mode, count_override=args.count, bank_override=args.bank)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_exam_runner.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add exam_runner.py tests/test_exam_runner.py
git commit -m "feat: exam runner CLI with full and random modes"
```

---

### Task 7: Examiner Module (Claude Code Helper)

**Files:**
- Create: `examiner.py`

This module is a helper script that Claude Code reads and executes during a session. It does NOT call any API — Claude Code itself acts as the examiner.

- [ ] **Step 1: Create examiner.py**

```python
"""
Examiner Helper — 供 Claude Code 使用的出題輔助腳本。

使用方式（在 Claude Code session 中）：
  1. 使用者說「幫我出題」
  2. Claude Code 讀取此檔案了解流程
  3. Claude Code 讀取 specs/ 資料夾中的 spec 檔案
  4. Claude Code 讀取 prompts/examiner.yaml 取得出題 prompt
  5. Claude Code 依 prompt 產生題目
  6. Claude Code 呼叫 save_question_bank() 儲存題庫

此模組提供：
  - list_specs(): 列出 specs/ 資料夾中可用的 spec 檔案
  - save_question_bank(): 將題目存為 JSON 題庫檔
"""

import json
import os
from datetime import datetime
from typing import Dict, List


SPECS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs")
BANK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "question_bank")


def list_specs() -> List[str]:
    """列出 specs/ 中所有可用的 spec 檔案。"""
    if not os.path.exists(SPECS_DIR):
        os.makedirs(SPECS_DIR, exist_ok=True)
        return []

    exts = {".pdf", ".md", ".txt", ".log"}
    files = [
        f for f in os.listdir(SPECS_DIR)
        if os.path.isfile(os.path.join(SPECS_DIR, f))
        and os.path.splitext(f)[1].lower() in exts
    ]
    return sorted(files)


def save_question_bank(questions: List[Dict], spec_file: str, num_questions: int = None) -> str:
    """
    將題目儲存為題庫 JSON 檔。

    Args:
        questions: 題目 list，格式參見 question_bank schema
        spec_file: 來源 spec 檔名
        num_questions: 題目數量（預設自動計算）

    Returns:
        儲存的檔案路徑
    """
    os.makedirs(BANK_DIR, exist_ok=True)

    num = num_questions or len(questions)
    spec_name = os.path.splitext(spec_file)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{spec_name}_{num}q_{timestamp}.json"

    bank = {
        "metadata": {
            "spec_file": spec_file,
            "generated_at": datetime.now().isoformat(),
            "total_questions": num,
        },
        "questions": questions,
    }

    path = os.path.join(BANK_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

    print(f"題庫已儲存：{path}")
    return path


if __name__ == "__main__":
    specs = list_specs()
    if specs:
        print("可用的 spec 檔案：")
        for i, s in enumerate(specs, 1):
            print(f"  {i}. {s}")
    else:
        print("specs/ 資料夾中沒有檔案。請先放入 spec 檔案（支援 .pdf .md .txt .log）。")
```

- [ ] **Step 2: Commit**

```bash
git add examiner.py
git commit -m "feat: examiner helper module for Claude Code question generation"
```

---

### Task 8: Entry Points (BAT Files + User Guide)

**Files:**
- Create: `run_exam.bat`, `setup.bat`, `USER_GUIDE.md`

- [ ] **Step 1: Create setup.bat**

```bat
@echo off
chcp 65001 >nul
echo ================================
echo   Spec Benchmark - 環境安裝
echo ================================
echo.
echo 正在安裝 Python 套件...
pip install -r requirements.txt
echo.
echo ================================
echo   安裝完成！
echo   請先編輯 config.yaml 填入 Nexus 認證資訊
echo ================================
pause
```

- [ ] **Step 2: Create run_exam.bat**

```bat
@echo off
chcp 65001 >nul
echo.
python exam_runner.py
echo.
pause
```

- [ ] **Step 3: Create USER_GUIDE.md**

```markdown
# Spec Benchmark Test System - 使用指南

## 快速開始

### 1. 首次安裝

雙擊 `setup.bat`，或手動執行：

```bash
pip install -r requirements.txt
```

### 2. 填寫設定

編輯 `config.yaml`：

```yaml
credentials:
  examinee:
    user_key: "你的答題者 API Key"
    share_code: "你的答題者 Share Code"
  judge:
    user_key: "你的裁判 API Key"
    share_code: "你的裁判 Share Code"

exam:
  question_bank: "question_bank/你的題庫.json"  # 題庫檔案路徑
  default_mode: "full"                           # full=全考 / random=隨機抽題
  default_random_count: 20                       # 隨機模式抽幾題
```

### 3. 執行考試

雙擊 `run_exam.bat`，或手動執行：

```bash
python exam_runner.py
```

進階選項（覆蓋 config 設定）：

```bash
# 隨機抽 30 題
python exam_runner.py --mode random --count 30

# 指定不同題庫
python exam_runner.py --bank question_bank/other.json
```

### 4. 查看報告

考試完成後，報告會存在 `results/` 資料夾：

| 檔案 | 說明 |
|------|------|
| `exam_YYYYMMDD_HHMMSS.html` | 視覺化報告，雙擊開啟 |
| `exam_YYYYMMDD_HHMMSS.json` | 結構化資料，程式可讀 |
| `exam_YYYYMMDD_HHMMSS_suggestions.md` | 改善建議，可直接複製貼上 |

---

## 出題（需要 Claude Code）

出題流程在 Claude Code session 中執行，不需要額外 API 費用。

### 步驟

1. 把 spec 檔案放到 `specs/` 資料夾
2. 開啟 Claude Code，進入本專案目錄
3. 告訴 Claude：「幫我用 specs/你的檔案.md 出 100 題」
4. Claude 會讀取 spec 和 `prompts/examiner.yaml`，產生題庫
5. 題庫存入 `question_bank/` 資料夾
6. 到 `config.yaml` 把 `question_bank` 路徑指向新題庫

### 注意事項

- 出題不需要每次執行，題庫可重複使用
- 預設出 100 題（60% 問答、40% 選擇）
- 可修改 `prompts/examiner.yaml` 調整出題方式

---

## 自訂 Prompt

三份 prompt 模板在 `prompts/` 資料夾，直接編輯 YAML 檔即可：

| 檔案 | 角色 | 用途 |
|------|------|------|
| `examiner.yaml` | 出題者 | 控制出題方式和格式 |
| `examinee.yaml` | 答題者 | 控制答題行為和風格 |
| `judge.yaml` | 裁判 | 控制評分標準和建議格式 |

模板中的 `{{變數}}` 會在執行時自動替換，不需要改程式碼。

---

## 專案結構

```
spec-benchmark-test/
├── specs/              ← 放 spec 檔案（PDF/MD/TXT/LOG）
├── prompts/            ← Prompt 模板（可自訂）
├── question_bank/      ← 題庫 JSON
├── results/            ← 考試報告
├── config.yaml         ← 設定檔（填 API Key 和選項）
├── run_exam.bat        ← 雙擊執行考試
├── setup.bat           ← 雙擊安裝環境
└── exam_runner.py      ← 考試主程式
```

---

## FAQ

**Q: 可以用不同的 AI 模型當裁判和答題者嗎？**
A: 可以。在 `config.yaml` 中，`examinee` 和 `judge` 分別設定不同的 `share_code`，指向不同的 Nexus 模型。

**Q: 如何追蹤分數進步？**
A: 每次考試都會產出帶時間戳的 JSON 檔，可以比較不同次考試的 `average_score`。

**Q: 題庫可以手動編輯嗎？**
A: 可以。題庫是 JSON 格式，可以直接編輯增刪題目。

**Q: 改善建議怎麼用？**
A: 打開 `_suggestions.md` 檔，複製「綜合改善建議」區段，貼到地端 AI 的 system prompt 或規則中。
```

- [ ] **Step 4: Commit**

```bash
git add run_exam.bat setup.bat USER_GUIDE.md
git commit -m "feat: add bat launchers and user guide"
```

---

### Task 9: Integration Test & Polish

**Files:**
- Create: `question_bank/example_5q.json` (small test bank for dry-run)

- [ ] **Step 1: Create example question bank for testing**

Create `question_bank/example_5q.json`:

```json
{
  "metadata": {
    "spec_file": "example_spec.md",
    "generated_at": "2026-03-28T00:00:00",
    "total_questions": 5
  },
  "questions": [
    {
      "id": 1,
      "type": "qa",
      "difficulty": "easy",
      "question": "請說明 HTTP 200 狀態碼的含義。",
      "reference_answer": "HTTP 200 表示請求成功。伺服器已成功處理了請求，並回傳了所請求的資源。",
      "source_section": "2.1 HTTP Status Codes"
    },
    {
      "id": 2,
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "HTTP 404 狀態碼代表什麼？",
      "options": ["A) 伺服器錯誤", "B) 未授權", "C) 找不到資源", "D) 請求逾時"],
      "correct_answer": "C",
      "explanation": "404 Not Found 表示伺服器找不到請求的資源。",
      "source_section": "2.1 HTTP Status Codes"
    },
    {
      "id": 3,
      "type": "qa",
      "difficulty": "medium",
      "question": "請解釋 REST API 中 GET 和 POST 方法的主要區別。",
      "reference_answer": "GET 用於讀取資源，是冪等且安全的操作，參數透過 URL 傳遞。POST 用於建立新資源，不是冪等的，參數透過 request body 傳遞。",
      "source_section": "3.1 HTTP Methods"
    },
    {
      "id": 4,
      "type": "multiple_choice",
      "difficulty": "medium",
      "question": "RESTful API 中，哪個 HTTP 方法通常用於更新已存在的資源？",
      "options": ["A) GET", "B) POST", "C) PUT", "D) DELETE"],
      "correct_answer": "C",
      "explanation": "PUT 方法用於更新或替換已存在的資源。",
      "source_section": "3.1 HTTP Methods"
    },
    {
      "id": 5,
      "type": "qa",
      "difficulty": "hard",
      "question": "請說明 OAuth 2.0 的 Authorization Code Flow 的完整流程。",
      "reference_answer": "1) 客戶端將使用者導向授權伺服器。2) 使用者授權後，授權伺服器回傳 authorization code 到 redirect URI。3) 客戶端用 authorization code 向授權伺服器換取 access token。4) 客戶端使用 access token 存取受保護的資源。",
      "source_section": "5.2 OAuth 2.0"
    }
  ]
}
```

- [ ] **Step 2: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 3: Dry-run verification (without real Nexus API)**

Verify the CLI starts and parses config correctly:

```bash
python exam_runner.py --help
```

Expected output showing usage and options.

- [ ] **Step 4: Update config.yaml to point to example bank**

Update `config.yaml`:

```yaml
exam:
  question_bank: "question_bank/example_5q.json"
```

- [ ] **Step 5: Final commit**

```bash
git add question_bank/example_5q.json config.yaml
git commit -m "feat: add example question bank and complete integration"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Project scaffolding | config.yaml, requirements.txt, prompts/*.yaml |
| 2 | Prompt loader | prompt_loader.py, tests/test_prompt_loader.py |
| 3 | Nexus client sync | nexus_client.py (add sync methods) |
| 4 | Judge module | judge.py |
| 5 | Report generator | report_generator.py, templates/report.html |
| 6 | Exam runner CLI | exam_runner.py, tests/test_exam_runner.py |
| 7 | Examiner helper | examiner.py |
| 8 | Entry points | run_exam.bat, setup.bat, USER_GUIDE.md |
| 9 | Integration test | question_bank/example_5q.json |
