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


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load config.yaml and return as dict."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_questions(questions: List[Dict], mode: str, random_count: int) -> List[Dict]:
    """Select questions based on mode: 'full' returns all, 'random' samples random_count."""
    if mode == "random":
        count = min(random_count, len(questions))
        return random.sample(questions, count)
    return list(questions)


def run_exam(config: Dict, mode_override: str = None, count_override: int = None, bank_override: str = None):
    """Execute the full exam: load questions, answer, judge, report."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, config["paths"]["prompts_dir"])
    results_dir = os.path.join(base_dir, config["paths"]["results_dir"])
    templates_dir = os.path.join(base_dir, "templates")

    bank_path = bank_override or config["exam"]["question_bank"]
    if not os.path.isabs(bank_path):
        bank_path = os.path.join(base_dir, bank_path)

    mode = mode_override or config["exam"]["default_mode"]
    random_count = count_override or config["exam"]["default_random_count"]

    logger.info(f"載入題庫：{bank_path}")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    questions = select_questions(bank["questions"], mode, random_count)
    total = len(questions)
    logger.info(f"考試模式：{mode} | 題數：{total}")

    prompt_loader = PromptLoader(prompts_dir)

    examinee_client = NexusClient(config["credentials"]["examinee"]["user_key"])
    examinee_share_code = config["credentials"]["examinee"]["share_code"]

    judge_client = NexusClient(config["credentials"]["judge"]["user_key"])
    judge_share_code = config["credentials"]["judge"]["share_code"]
    judge = Judge(judge_client, judge_share_code, prompt_loader)

    now = datetime.now()
    exam_id = f"exam_{now.strftime('%Y%m%d_%H%M%S')}"
    results = []
    score_sum = 0

    for i, q in enumerate(questions):
        q_num = i + 1
        q_type = q.get("type", "qa")

        if q_type == "multiple_choice":
            question_text = q["question"] + "\n" + "\n".join(q.get("options", []))
        else:
            question_text = q["question"]

        examinee_prompt = prompt_loader.render("examinee", {"question": question_text})
        history = [{"role": 1, "content": examinee_prompt}]
        print(f"\r  [{q_num}/{total}] 答題中...", end="", flush=True)
        examinee_answer = examinee_client.generate_response_sync(examinee_share_code, history)

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

    average_score = score_sum / total if total > 0 else 0
    print(f"\n  全部作答完畢！平均分數：{average_score:.1f}")
    print("  正在產生綜合建議...")

    overall_suggestion = judge.generate_overall_suggestion(results, average_score)

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

    report_gen = ReportGenerator(results_dir, templates_dir)
    report_gen.generate_all(exam_data)

    print(f"\n  報告已產出：")
    print(f"    HTML:  {results_dir}/{exam_id}.html")
    print(f"    JSON:  {results_dir}/{exam_id}.json")
    print(f"    建議:  {results_dir}/{exam_id}_suggestions.md")

    return exam_data


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
