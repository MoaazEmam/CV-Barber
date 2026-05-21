from app.llm.prompt_loader import load_prompt


class TestPrompts:
    def test_parser_user_prompt_formats_cv_text(self):
        result = load_prompt("parser_user").format(cv_text="my cv content")
        assert "my cv content" in result

    def test_scorer_system_prompt_formats_top_n(self):
        result = load_prompt("scorer_system").format(
            top_n_experience=3,
            top_n_projects=5,
        )
        assert "3" in result
        assert "5" in result

    def test_scorer_user_prompt_formats_all_fields(self):
        result = load_prompt("scorer_user").format(
            job_title="SWE Intern",
            company_name="Acme",
            job_description="We need a backend developer",
            master_cv_json='{"full_name": "Moaaz"}',
        )
        assert "SWE Intern" in result
        assert "Acme" in result
        assert "We need a backend developer" in result
        assert "Moaaz" in result

    def test_parser_system_prompt_is_not_empty(self):
        assert len(load_prompt("parser_system")) > 50

    def test_scorer_system_prompt_mentions_scoring(self):
        result = load_prompt("scorer_system").format(
            top_n_experience=3,
            top_n_projects=5,
        )
        assert "score" in result.lower()
