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
    level=logging.WARNING,
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


def _save_json_atomic(path: str, data: Dict):
    """Write JSON file (overwrite)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Answer Only Mode ──────────────────────────────────────
def run_answer_only(config: Dict, mode_override: str = None, count_override: int = None, bank_override: str = None):
    """Only collect answers from Nexus examinee, no judging. Saves after each question."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, config["paths"]["prompts_dir"])
    results_dir = os.path.join(base_dir, config["paths"]["results_dir"])
    os.makedirs(results_dir, exist_ok=True)

    bank_path = bank_override or config["exam"]["question_bank"]
    if not os.path.isabs(bank_path):
        bank_path = os.path.join(base_dir, bank_path)

    mode = mode_override or config["exam"]["default_mode"]
    random_count = count_override or config["exam"]["default_random_count"]

    print(f"  Loading question bank: {os.path.basename(bank_path)}")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    questions = select_questions(bank["questions"], mode, random_count)
    total = len(questions)
    print(f"  Mode: {mode} | Questions: {total}")
    print()

    prompt_loader = PromptLoader(prompts_dir)

    examinee_client = NexusClient(config["credentials"]["examinee"]["user_key"])
    examinee_share_code = config["credentials"]["examinee"]["share_code"]

    now = datetime.now()
    exam_id = f"answers_{now.strftime('%Y%m%d_%H%M%S')}"
    answers_path = os.path.join(results_dir, f"{exam_id}.json")

    answers_data = {
        "exam_id": exam_id,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "question_bank": os.path.basename(bank_path),
        "mode": mode,
        "total_questions": total,
        "completed_questions": 0,
        "examinee_share_code": examinee_share_code,
        "answers": [],
    }

    # Save empty file first
    _save_json_atomic(answers_path, answers_data)

    for i, q in enumerate(questions):
        q_num = i + 1
        q_type = q.get("type", "qa")

        if q_type == "multiple_choice":
            question_text = q["question"] + "\n" + "\n".join(q.get("options", []))
        else:
            question_text = q["question"]

        examinee_prompt = prompt_loader.render("examinee", {"question": question_text})
        history = [{"role": 1, "content": examinee_prompt}]

        print(f"  [{q_num}/{total}] Answering Q{q['id']}...", end=" ", flush=True)
        examinee_answer = examinee_client.generate_response_sync(examinee_share_code, history)

        answers_data["answers"].append({
            "question_id": q["id"],
            "examinee_answer": examinee_answer,
        })
        answers_data["completed_questions"] = q_num

        # Save after each question
        _save_json_atomic(answers_path, answers_data)

        is_error = examinee_answer.startswith("[ERROR]")
        status = "ERROR" if is_error else "Done"
        print(f"{status} (saved)")

    print()
    print(f"  All {total} questions answered!")
    print(f"  Answers saved: {answers_path}")
    print()
    print(f"  Next: bring this file to Claude Code for judging")

    return answers_data


# ─── Full Exam Mode ────────────────────────────────────────
def run_exam(config: Dict, mode_override: str = None, count_override: int = None, bank_override: str = None):
    """Execute the full exam: answer + judge + report. Also saves answers.json for later re-judging."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, config["paths"]["prompts_dir"])
    results_dir = os.path.join(base_dir, config["paths"]["results_dir"])
    templates_dir = os.path.join(base_dir, "templates")
    os.makedirs(results_dir, exist_ok=True)

    bank_path = bank_override or config["exam"]["question_bank"]
    if not os.path.isabs(bank_path):
        bank_path = os.path.join(base_dir, bank_path)

    mode = mode_override or config["exam"]["default_mode"]
    random_count = count_override or config["exam"]["default_random_count"]

    print(f"  Loading question bank: {os.path.basename(bank_path)}")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    questions = select_questions(bank["questions"], mode, random_count)
    total = len(questions)
    print(f"  Mode: {mode} | Questions: {total}")
    print()

    prompt_loader = PromptLoader(prompts_dir)

    examinee_client = NexusClient(config["credentials"]["examinee"]["user_key"])
    examinee_share_code = config["credentials"]["examinee"]["share_code"]

    judge_client = NexusClient(config["credentials"]["judge"]["user_key"])
    judge_share_code = config["credentials"]["judge"]["share_code"]
    judge = Judge(judge_client, judge_share_code, prompt_loader)

    now = datetime.now()
    exam_id = f"exam_{now.strftime('%Y%m%d_%H%M%S')}"

    # Also prepare answers.json for later re-judging
    answers_path = os.path.join(results_dir, f"answers_{now.strftime('%Y%m%d_%H%M%S')}.json")
    answers_data = {
        "exam_id": f"answers_{now.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "question_bank": os.path.basename(bank_path),
        "mode": mode,
        "total_questions": total,
        "completed_questions": 0,
        "examinee_share_code": examinee_share_code,
        "answers": [],
    }

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

        print(f"  [{q_num}/{total}] Answering Q{q['id']}...", end=" ", flush=True)
        examinee_answer = examinee_client.generate_response_sync(examinee_share_code, history)

        # Save answer incrementally
        answers_data["answers"].append({
            "question_id": q["id"],
            "examinee_answer": examinee_answer,
        })
        answers_data["completed_questions"] = q_num
        _save_json_atomic(answers_path, answers_data)

        print(f"Judging...", end=" ", flush=True)
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

        status_icon = "O" if score >= 60 else "X"
        print(f"{status_icon} {score}pts (avg: {avg_so_far:.1f})")

    average_score = score_sum / total if total > 0 else 0
    print()
    print(f"  All done! Average score: {average_score:.1f}")
    print(f"  Generating overall suggestion...")

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

    print()
    print(f"  Reports generated:")
    print(f"    HTML:      results/{exam_id}.html")
    print(f"    JSON:      results/{exam_id}.json")
    print(f"    Suggest:   results/{exam_id}_suggestions.md")
    print(f"    Answers:   {os.path.basename(answers_path)} (for re-judging)")

    return exam_data


# ─── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Spec Benchmark Exam System")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["full", "random"], help="Exam mode (overrides config)")
    parser.add_argument("--count", type=int, help="Random question count (overrides config)")
    parser.add_argument("--bank", help="Question bank file path (overrides config)")
    parser.add_argument("--answer-only", action="store_true", help="Answer only, no judging. Output answers JSON for later evaluation")
    args = parser.parse_args()

    print()
    print("=" * 50)
    print("  Spec Benchmark Exam System")
    print("=" * 50)

    config = load_config(args.config)

    if args.answer_only:
        print("  >> Answer-only mode (no judging)")
    else:
        print("  >> Full exam mode (answer + judge)")
    print("=" * 50)
    print()

    if args.answer_only:
        run_answer_only(config, mode_override=args.mode, count_override=args.count, bank_override=args.bank)
    else:
        run_exam(config, mode_override=args.mode, count_override=args.count, bank_override=args.bank)


if __name__ == "__main__":
    main()
