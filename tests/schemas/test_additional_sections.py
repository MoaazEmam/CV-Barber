from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


def test_master_cv_preserves_additional_sections():
    m = MasterCV(
        full_name="X",
        additional_sections=[
            {"title": "Honors & Awards", "entries": [
                {"heading": "NASA Apps", "subheading": "First Place (2022)", "bullets": ["Won"]},
            ]},
            {"title": "Languages", "entries": [{"detail": "Arabic (Native); English (Fluent)"}]},
        ],
    )
    dumped = m.model_dump()
    assert len(dumped["additional_sections"]) == 2
    assert dumped["additional_sections"][0]["title"] == "Honors & Awards"
    assert dumped["additional_sections"][0]["entries"][0]["subheading"] == "First Place (2022)"
    # round-trips back through validation (what parsed_data does)
    again = MasterCV.model_validate(dumped)
    assert again.additional_sections[1].entries[0].detail.startswith("Arabic")


def test_tailored_cv_accepts_additional_sections():
    t = TailoredCV(
        full_name="X", job_title="Eng", company_name="Co",
        additional_sections=[{"title": "Languages", "entries": [{"detail": "EN"}]}],
    )
    assert t.additional_sections[0].title == "Languages"


def test_additional_sections_default_empty():
    assert MasterCV(full_name="X").additional_sections == []
    assert TailoredCV(full_name="X", job_title="E", company_name="C").additional_sections == []


def test_coerces_loose_llm_shapes():
    # bullets as a bare string, detail as a list, an entry as a bare string.
    m = MasterCV(full_name="X", additional_sections=[
        {"title": "Awards", "entries": [
            {"heading": "Prize", "bullets": "Single bullet as a string"},
            "A bare-string entry",
        ]},
        {"title": "Languages", "entries": [{"detail": ["English", "Spanish"]}]},
    ])
    awards = m.additional_sections[0]
    assert awards.entries[0].bullets == ["Single bullet as a string"]
    assert awards.entries[1].detail == "A bare-string entry"
    assert m.additional_sections[1].entries[0].detail == "English; Spanish"


def test_coerces_dict_of_sections():
    # LLM sometimes emits {title: entries} instead of a list.
    m = MasterCV.model_validate({
        "full_name": "X",
        "additional_sections": {"Honors": [{"heading": "Dean's List"}]},
    })
    assert len(m.additional_sections) == 1
    assert m.additional_sections[0].title == "Honors"
    assert m.additional_sections[0].entries[0].heading == "Dean's List"


def test_titleless_sections_dropped():
    m = MasterCV(full_name="X", additional_sections=[{"entries": []}, {"title": "Keep"}])
    assert [s.title for s in m.additional_sections] == ["Keep"]
