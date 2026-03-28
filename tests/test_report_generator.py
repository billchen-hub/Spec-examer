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
