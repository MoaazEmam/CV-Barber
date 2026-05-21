import pytest

from app.llm.prompt_loader import load_prompt


class TestLoadPrompt:
    @pytest.mark.parametrize(
        "name",
        [
            "parser_system",
            "parser_user",
            "scorer_system",
            "scorer_user",
            "qa_system",
            "qa_user",
            "ats_general_system",
            "ats_general_user",
            "ats_job_system",
            "ats_job_user",
        ],
    )
    def test_each_known_prompt_loads_non_empty(self, name):
        content = load_prompt(name)
        assert content and len(content) > 20

    def test_missing_prompt_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("definitely_does_not_exist_xyz")
