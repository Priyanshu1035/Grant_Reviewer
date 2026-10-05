from .ai_service import extract_requirements


def main():

    guideline_text = """
    Grant Application Guidelines

    1. Eligibility

    Applicants must be registered non-profit organizations.

    Applicants must have been operating for at least two years.

    2. Project Proposal

    Applicants must provide a detailed description of the proposed project.

    The proposal should explain how the project benefits the target community.

    3. Budget

    Applicants must provide a detailed project budget.

    4. Timeline

    Applicants should provide an estimated project timeline.

    5. Supporting Documents

    Applicants must submit proof of non-profit registration.

    Applicants must submit the organization's latest annual report.
    """

    requirements = extract_requirements(guideline_text)

    print("\nExtracted requirements:\n")

    for index, requirement in enumerate(requirements, start=1):

        print(f"Requirement {index}")
        print(f"  Description: {requirement.requirement}")
        print(f"  Mandatory:   {requirement.mandatory}")
        print(f"  Category:     {requirement.category}")
        print(f"  Source:       {requirement.source_text}")
        print()


if __name__ == "__main__":
    main()