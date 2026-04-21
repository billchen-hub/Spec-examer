import argparse
import json
import logging
import os
import random
import re
import sys
from datetime import datetime
from typing import Dict, List

import yaml

from nexus_client import NexusClient
from prompt_loader import PromptLoader
from judge import Judge
from report_generator import ReportGenerator
from spec_loader import SpecLoadError, load_spec_content

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


def get_api_key(config: Dict, role: str = None) -> str:
    """Get API key: shared key or per-role key (backward compatible)."""
    creds = config["credentials"]
    # Shared key (new format)
    if "api_key" in creds:
        return creds["api_key"]
    # Per-role key (old format)
    if role and role in creds and "user_key" in creds[role]:
        return creds[role]["user_key"]
    raise ValueError(f"No API key found in config for role: {role}")


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


# ─── Generate Questions Mode ──────────────────────────────
def _derive_bank_name(spec_inputs: List[str], base_dir: str) -> str:
    """Pick a stem for the output question-bank filename.

    Rules:
      - Single file  -> its stem (e.g. "ufs_spec_v4.1")
      - Single dir   -> the directory's basename
      - Multiple     -> first input's stem + "_and_{n-1}_more"
    """
    def _stem(p: str) -> str:
        path = p if os.path.isabs(p) else os.path.join(base_dir, p)
        path = os.path.normpath(path)
        if os.path.isdir(path):
            return os.path.basename(path.rstrip(os.sep)) or "specs"
        return os.path.splitext(os.path.basename(path))[0] or "specs"

    if len(spec_inputs) == 1:
        return _stem(spec_inputs[0]) or "specs"
    return f"{_stem(spec_inputs[0])}_and_{len(spec_inputs) - 1}_more"


def run_generate(config: Dict, spec_inputs: List[str], num_questions: int = None):
    """Use Nexus AI to generate questions from one or more spec files/folders.

    `spec_inputs` may mix files and directories. Supported extensions:
    .pdf / .md / .txt / .log. Directories are scanned recursively.
    """

    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, config["paths"]["prompts_dir"])
    bank_dir = os.path.join(base_dir, config["paths"]["question_bank_dir"])
    os.makedirs(bank_dir, exist_ok=True)

    num_questions = num_questions or config["exam"].get("default_question_count", 100)

    # Resolve inputs relative to project root if not absolute.
    resolved_inputs = [
        p if os.path.isabs(p) else os.path.join(base_dir, p)
        for p in spec_inputs
    ]

    print(f"  Spec inputs: {len(spec_inputs)}")
    for p in spec_inputs:
        print(f"    - {p}")
    print(f"  Questions to generate: {num_questions}")
    print()

    # Load spec content (handles PDF + text, files + folders).
    print(f"  Reading spec files...", end=" ", flush=True)
    try:
        spec = load_spec_content(resolved_inputs, base_dir=base_dir)
    except SpecLoadError as e:
        print("FAILED")
        print(f"  ERROR: {e}")
        return None
    file_count = len(spec["files"])
    print(f"Done ({file_count} file(s), {spec['total_chars']} chars)")
    for display, text in spec["files"]:
        print(f"    - {display} ({len(text)} chars)")

    # Load examiner prompt
    prompt_loader = PromptLoader(prompts_dir)
    examiner_prompt = prompt_loader.render("examiner", {
        "num_questions": str(num_questions),
    })

    # Combine prompt + spec content
    full_prompt = examiner_prompt + "\n\n--- SPEC CONTENT ---\n\n" + spec["combined"]

    # Call Nexus
    api_key = get_api_key(config, "examiner")
    examiner_share_code = config["credentials"]["examiner"]["share_code"]
    client = NexusClient(api_key)

    print(f"  Calling Nexus AI to generate questions...", end=" ", flush=True)
    history = [{"role": 1, "content": full_prompt}]
    response = client.generate_response_sync(examiner_share_code, history)
    print("Done")

    if response.startswith("[ERROR]"):
        print(f"  {response}")
        return None

    # Parse JSON from response
    print(f"  Parsing response...", end=" ", flush=True)
    questions = _parse_questions_response(response)

    if not questions:
        # Save raw response for debugging
        raw_path = os.path.join(bank_dir, f"raw_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(response)
        print(f"FAILED")
        print(f"  Could not parse questions from response.")
        print(f"  Raw response saved: {raw_path}")
        return None

    print(f"OK ({len(questions)} questions)")

    # Save question bank
    stem = _derive_bank_name(spec_inputs, base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{stem}_{len(questions)}q_{timestamp}.json"
    bank_path = os.path.join(bank_dir, filename)

    source_files = [display for display, _ in spec["files"]]
    bank_data = {
        "metadata": {
            # Keep legacy "spec_file" field so older consumers don't break.
            "spec_file": source_files[0] if len(source_files) == 1 else f"{len(source_files)} files",
            "spec_inputs": spec_inputs,
            "source_files": source_files,
            "generated_at": datetime.now().isoformat(),
            "generated_by": "nexus",
            "examiner_share_code": examiner_share_code,
            "total_questions": len(questions),
        },
        "questions": questions,
    }
    _save_json_atomic(bank_path, bank_data)

    print()
    print(f"  Question bank saved: {bank_path}")
    print(f"  Total questions: {len(questions)}")
    print()
    print(f"  To use this bank, update config.yaml:")
    print(f'    question_bank: "question_bank/{filename}"')

    return bank_data


def _parse_questions_response(response: str) -> list:
    """Try to extract questions JSON array from Nexus response."""
    # Try 1: full JSON with "questions" key
    try:
        data = json.loads(response)
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try 2: find JSON block in response
    patterns = [
        r'\{\s*"questions"\s*:\s*\[.*?\]\s*\}',  # {"questions": [...]}
        r'\[.*?\]',  # bare array
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, dict) and "questions" in data:
                    return data["questions"]
                if isinstance(data, list) and len(data) > 0:
                    return data
            except json.JSONDecodeError:
                continue

    return None


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

    api_key = get_api_key(config, "examinee")
    examinee_client = NexusClient(api_key)
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

    api_key = get_api_key(config, "examinee")
    examinee_client = NexusClient(api_key)
    examinee_share_code = config["credentials"]["examinee"]["share_code"]

    judge_api_key = get_api_key(config, "judge")
    judge_client = NexusClient(judge_api_key)
    judge_share_code = config["credentials"]["judge"]["share_code"]
    judge = Judge(judge_client, judge_share_code, prompt_loader)

    now = datetime.now()
    exam_id = f"exam_{now.strftime('%Y%m%d_%H%M%S')}"

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

    # Exam mode args
    parser.add_argument("--mode", choices=["full", "random"], help="Exam mode (overrides config)")
    parser.add_argument("--count", type=int, help="Random question count (overrides config)")
    parser.add_argument("--bank", help="Question bank file path (overrides config)")
    parser.add_argument("--answer-only", action="store_true", help="Answer only, no judging")

    # Generate mode args
    parser.add_argument(
        "--generate",
        nargs="+",
        metavar="SPEC_PATH",
        help="Generate questions from one or more spec files or folders "
             "(supports .pdf/.md/.txt/.log; folders are scanned recursively) "
             "via Nexus AI",
    )
    parser.add_argument("--num-questions", type=int, help="Number of questions to generate (default from config)")

    args = parser.parse_args()

    print()
    print("=" * 50)
    print("  Spec Benchmark Exam System")
    print("=" * 50)

    config = load_config(args.config)

    if args.generate:
        print("  >> Generate mode (Nexus AI creates questions)")
        print("=" * 50)
        print()
        run_generate(config, spec_inputs=args.generate, num_questions=args.num_questions)
    elif args.answer_only:
        print("  >> Answer-only mode (no judging)")
        print("=" * 50)
        print()
        run_answer_only(config, mode_override=args.mode, count_override=args.count, bank_override=args.bank)
    else:
        print("  >> Full exam mode (answer + judge)")
        print("=" * 50)
        print()
        run_exam(config, mode_override=args.mode, count_override=args.count, bank_override=args.bank)


if __name__ == "__main__":
    main()
