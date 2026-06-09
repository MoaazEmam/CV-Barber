from app.pipeline.pdf.render import _build_env, latex_escape


def test_latex_escape_special_chars():
    assert latex_escape("A & B") == r"A \& B"
    assert latex_escape("100% done_now #1") == r"100\% done\_now \#1"
    assert latex_escape(None) == ""


def test_env_fills_var_and_block_loop_with_escaping():
    env = _build_env()
    template = env.from_string(
        r"\VAR{ cv.full_name }: "
        r"\BLOCK{ for e in cv.experience }[\VAR{ e.title }]\BLOCK{ endfor }"
    )
    out = template.render(
        cv={
            "full_name": "A & Co",
            "experience": [{"title": "Eng_1"}, {"title": "Eng_2"}],
        }
    )
    assert out == r"A \& Co: [Eng\_1][Eng\_2]"


def test_missing_optional_field_renders_empty():
    env = _build_env()
    template = env.from_string(r"\VAR{ cv.email }")
    assert template.render(cv={}) == ""
