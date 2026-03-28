import json
import logging
import re
from typing import Dict, List

from nexus_client import NexusClient
from prompt_loader import PromptLoader

logger = logging.getLogger("[Judge]")


class Judge:
    """Calls Nexus judge API to score examinee answers."""

    def __init__(self, nexus_client: NexusClient, share_code: str, prompt_loader: PromptLoader):
        self.client = nexus_client
        self.share_code = share_code
        self.prompt_loader = prompt_loader

    def score_answer(self, question: Dict, examinee_answer: str) -> Dict:
        """Score a single answer. Returns dict with score, feedback, improvement_suggestion."""
        q_type = question.get("type", "qa")
        if q_type == "multiple_choice":
            ref_answer = f"正確答案：{question.get('correct_answer', '')}\n解釋：{question.get('explanation', '')}"
            question_text = question["question"] + "\n" + "\n".join(question.get("options", []))
        else:
            ref_answer = question.get("reference_answer", "")
            question_text = question["question"]

        prompt = self.prompt_loader.render("judge", {
            "question_type": "選擇題" if q_type == "multiple_choice" else "問答題",
            "question": question_text,
            "reference_answer": ref_answer,
            "examinee_answer": examinee_answer,
        })

        history = [{"role": 1, "content": prompt}]
        response = self.client.generate_response_sync(self.share_code, history)

        return self._parse_response(response)

    def generate_overall_suggestion(self, results: List[Dict], average_score: float) -> str:
        """Generate overall improvement suggestion from all results."""
        summary_lines = []
        for r in results:
            summary_lines.append(
                f"第 {r['question_id']} 題（{r['score']} 分）：{r.get('judge_feedback', '')[:100]}"
            )
        results_summary = "\n".join(summary_lines)

        prompt = self.prompt_loader.render("judge", {
            "results_summary": results_summary,
            "average_score": str(average_score),
        }, template_key="overall_template")

        history = [{"role": 1, "content": prompt}]
        return self.client.generate_response_sync(self.share_code, history)

    def _parse_response(self, response: str) -> Dict:
        """Parse judge JSON response. Fallback to defaults if parsing fails."""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "score": max(0, min(100, int(data.get("score", 0)))),
                    "feedback": data.get("feedback", ""),
                    "improvement_suggestion": data.get("improvement_suggestion", ""),
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse judge response as JSON: {e}")

        # Fallback: return the raw response as feedback with score 0
        return {
            "score": 0,
            "feedback": f"[裁判回應無法解析] {response[:500]}",
            "improvement_suggestion": "",
        }
