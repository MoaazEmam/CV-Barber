from app.pipeline import dedup


def test_normalize_collapses_whitespace_and_lowercases():
    assert dedup.normalize("  Hello   World\n\tFoo ") == "hello world foo"


def test_hash_is_stable_and_case_insensitive():
    a = dedup.text_hash("John Doe — Engineer")
    b = dedup.text_hash("  john   doe — engineer ")
    assert a == b
    assert len(a) == 64


def test_hash_differs_for_different_content():
    assert dedup.text_hash("alpha") != dedup.text_hash("beta")
