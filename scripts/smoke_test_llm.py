def main():
    from app.extraction import TextExtractor
    from app.llm import CVParser, CVScorer
    from app.schemas.config import TailoringConfig

    extractor = TextExtractor()
    text = extractor.extract_cv_text("tests/extraction/fixtures/sample.pdf")
    print(f"Extracted {len(text)} characters\n")

    parser = CVParser()
    master_cv = parser.parse(text)

    print("=" * 60)
    print("MASTER CV (full parsed structure)")
    print("=" * 60)
    print(master_cv.model_dump_json(indent=2))

    config = TailoringConfig(
        job_title="Backend Engineering Intern",
        company_name="Acme Corp",
    )

    scorer = CVScorer()
    tailored = scorer.score(
        master_cv,
        "We are looking for a backend developer with Python and API experience.",
        config,
    )

    print("\n")
    print("=" * 60)
    print("TAILORED CV (filtered and scored)")
    print("=" * 60)
    print(tailored.model_dump_json(indent=2))


if __name__ == "__main__":
    main()