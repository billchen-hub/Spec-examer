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
