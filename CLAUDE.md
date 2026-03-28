# Spec Benchmark Test System

## Overview
針對 spec 文件的 AI 能力評測系統。出題者（Claude Code）產生題庫，答題者（Nexus AI）作答，裁判（Nexus AI）評分並提供改善建議。

## Architecture
- **出題流程**：Claude Code session 中執行，讀 `specs/` 裡的文件 → 產出題庫 JSON
- **考試流程**：獨立 Python CLI（`exam_runner.py`），呼叫 Nexus API → 產出 HTML/JSON/suggestions 報告

## Key Files
| File | Purpose |
|------|---------|
| `exam_runner.py` | 考試主程式 CLI |
| `examiner.py` | 出題輔助（Claude Code 用） |
| `judge.py` | 裁判評分模組 |
| `prompt_loader.py` | YAML prompt 模板載入 |
| `report_generator.py` | 報告產生（HTML/JSON/MD） |
| `nexus_client.py` | Nexus REST API 封裝 |
| `config.yaml` | 全域設定（認證、路徑、考試參數） |
| `prompts/*.yaml` | 可自訂的 prompt 模板 |

## Tech Stack
Python 3.10+, requests, PyYAML, Jinja2

## Development
```bash
pip install -r requirements.txt
python -m pytest tests/ -v    # 11 tests
python exam_runner.py --help  # CLI usage
```

## 出題流程（在 Claude Code 中）
1. 使用者把 spec 放入 `specs/`
2. 說「幫我出題」
3. Claude 讀 spec + `prompts/examiner.yaml`，產生題目
4. 用 `examiner.save_question_bank()` 存入 `question_bank/`
