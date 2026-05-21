from copy import deepcopy

from app.schemas.tailored_cv import TailoredCV


def apply_section_config(cv: TailoredCV, section_config: dict | None) -> TailoredCV:
    """Returns a copy of the CV with sections filtered per section_config.

    section_config shape:
      {
        "experience": {"enabled": bool, "subsections": {"experience.0": bool, ...}},
        ...
      }
    If a section's enabled is False, it is cleared entirely.
    If enabled is True, subsection entries set to False are filtered out of the list.
    """
    if not section_config:
        return cv

    data = cv.model_dump()

    list_section_keys = {"experience", "projects", "skills", "education"}
    cert_key = "certifications"

    for section_key in list(list_section_keys):
        section_state = section_config.get(section_key)
        if not section_state:
            continue
        if not section_state.get("enabled", True):
            data[section_key] = []
            continue
        subsections = section_state.get("subsections") or {}
        if subsections and section_key in data and isinstance(data[section_key], list):
            filtered = []
            for i, item in enumerate(data[section_key]):
                sub_key = f"{section_key}.{i}"
                if subsections.get(sub_key, True):
                    filtered.append(item)
            data[section_key] = filtered

    cert_state = section_config.get(cert_key)
    if cert_state and isinstance(data.get(cert_key), list):
        if not cert_state.get("enabled", True):
            data[cert_key] = []
        else:
            subsections = cert_state.get("subsections") or {}
            if subsections:
                filtered = []
                for i, item in enumerate(data[cert_key]):
                    sub_key = f"{cert_key}.{i}"
                    if subsections.get(sub_key, True):
                        filtered.append(item)
                data[cert_key] = filtered

    return TailoredCV.model_validate(data)
