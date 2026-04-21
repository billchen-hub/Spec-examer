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

from spec_loader import collect_spec_files


SPECS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs")
BANK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "question_bank")


def list_specs() -> List[str]:
    """列出 specs/ 中所有可用的 spec 檔案（含子資料夾，遞迴）。

    回傳的路徑是相對於 specs/ 的 posix-style 路徑，例如：
      "ufs_spec.pdf"
      "ufs spec md/chapters/03_terms.md"
    """
    if not os.path.exists(SPECS_DIR):
        os.makedirs(SPECS_DIR, exist_ok=True)
        return []

    files = collect_spec_files([SPECS_DIR])
    rel = [
        os.path.relpath(f, SPECS_DIR).replace(os.sep, "/")
        for f in files
    ]
    return sorted(rel)


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
