import os
import pytest
import tempfile
import yaml

from prompt_loader import PromptLoader


def make_yaml(tmp_path, filename, data):
    path = os.path.join(tmp_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


class TestPromptLoader:
    def test_load_prompt_file(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        result = loader.load("test")
        assert result["name"] == "test"
        assert "{{name}}" in result["template"]

    def test_render_with_variables(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("test", {"name": "Alice", "role": "judge"})
        assert rendered == "Hello Alice, you are judge."

    def test_render_missing_variable_left_as_is(self, tmp_path):
        data = {
            "name": "test",
            "description": "A test prompt",
            "template": "Hello {{name}}, you are {{role}}."
        }
        make_yaml(tmp_path, "test.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("test", {"name": "Alice"})
        assert rendered == "Hello Alice, you are {{role}}."

    def test_load_nonexistent_raises(self, tmp_path):
        loader = PromptLoader(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_render_named_template(self, tmp_path):
        data = {
            "name": "judge",
            "template": "Score: {{score}}",
            "overall_template": "Summary: {{summary}}"
        }
        make_yaml(tmp_path, "judge.yaml", data)
        loader = PromptLoader(str(tmp_path))
        rendered = loader.render("judge", {"summary": "Good"}, template_key="overall_template")
        assert rendered == "Summary: Good"
