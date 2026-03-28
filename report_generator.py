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
