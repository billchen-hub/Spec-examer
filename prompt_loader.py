import os
import re
import yaml
from typing import Dict, Optional


class PromptLoader:
    """Loads YAML prompt templates and renders them with variable substitution."""

    def __init__(self, prompts_dir: str):
        self.prompts_dir = prompts_dir

    def load(self, name: str) -> Dict:
        """Load a prompt YAML file by name (without .yaml extension)."""
        path = os.path.join(self.prompts_dir, f"{name}.yaml")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def render(self, name: str, variables: Dict[str, str], template_key: str = "template") -> str:
        """Load a prompt and substitute {{variable}} placeholders."""
        data = self.load(name)
        template = data.get(template_key, "")
        return self._substitute(template, variables)

    def _substitute(self, template: str, variables: Dict[str, str]) -> str:
        """Replace {{key}} with value. Leave unmatched placeholders as-is."""
        def replacer(match):
            key = match.group(1).strip()
            return str(variables.get(key, match.group(0)))
        return re.sub(r"\{\{(\s*\w+\s*)\}\}", replacer, template)
