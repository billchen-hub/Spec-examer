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
