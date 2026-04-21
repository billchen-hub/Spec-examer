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
| `spec_loader.py` | 載入 spec 檔案/資料夾（PDF/MD/TXT/LOG），供 `--generate` 使用 |
| `judge.py` | 裁判評分模組 |
| `prompt_loader.py` | YAML prompt 模板載入 |
| `report_generator.py` | 報告產生（HTML/JSON/MD） |
| `nexus_client.py` | Nexus REST API 封裝 |
| `config.yaml` | 全域設定（認證、路徑、考試參數） |
| `prompts/*.yaml` | 可自訂的 prompt 模板 |

## Tech Stack
Python 3.10+, requests, PyYAML, Jinja2, pypdf

## Development
```bash
pip install -r requirements.txt
python -m pytest tests/ -v    # 30 tests
python exam_runner.py --help  # CLI usage
```

## Nexus 出題輸入格式
`--generate` 接受**一或多個路徑**，檔案或資料夾皆可，並可混用：
- 支援副檔名：`.pdf`、`.md`、`.txt`、`.log`
- 資料夾遞迴掃描，自動跳過 `.git` / `__pycache__` / `node_modules` / `.venv` 等
- 每個檔案會在送給 AI 時加上 `--- FILE: <相對路徑> ---` 分隔標頭
- PDF 用 `pypdf` 抽文字；純圖片 PDF（無 OCR）會跳過並記錄警告

## 出題流程（在 Claude Code 中）
1. 使用者把 spec 放入 `specs/`
2. 說「幫我出題」
3. Claude 讀 spec + `prompts/examiner.yaml`，產生題目
4. 用 `examiner.save_question_bank()` 存入 `question_bank/`
