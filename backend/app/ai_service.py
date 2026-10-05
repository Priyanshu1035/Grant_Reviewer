import os
import json
import time

from dotenv import load_dotenv
from google import genai

from .schemas import (
    Requirement,
    RequirementMapping,
    EvidenceItem
)

load_dotenv()


# ============================================================
# Configuration
# ============================================================

AI_PROVIDER = os.getenv(
    "AI_PROVIDER",
    "gemini"
).lower()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if AI_PROVIDER == "gemini":

    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set"
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

else:
    client = None


# ============================================================
# Gemini
# ============================================================

def ask_gemini(prompt: str) -> str:

    max_retries = 3

    for attempt in range(max_retries):

        try:

            interaction = client.interactions.create(
                model="gemini-3.8-flash",
                input=prompt
            )

            return interaction.output_text

        except Exception as e:

            print(
                f"Gemini request failed "
                f"(attempt {attempt + 1}/{max_retries}): "
                f"{e}"
            )

            if attempt == max_retries - 1:
                raise

            time.sleep(
                2 ** attempt
            )


# ============================================================
# Requirement Extraction
# ============================================================

def extract_requirements(
    guideline_text: str
) -> list[Requirement]:

    if AI_PROVIDER == "mock":

        return mock_extract_requirements(
            guideline_text
        )

    prompt = f"""
You are reviewing a grant guideline.

Extract every requirement from the guideline.

For each requirement return:

- requirement: concise description
- mandatory: true or false
- category: eligibility, submission,
  supporting_document, budget, timeline, or other
- source_text: exact text from the guideline
  that establishes the requirement

Rules:

1. Do not invent requirements.
2. Only use information explicitly present
   in the guideline.
3. "must" means mandatory.
4. "should" means recommended, not mandatory.
5. Return ONLY valid JSON.
6. Return a JSON array.

Guideline:

{guideline_text}
"""

    response = ask_gemini(prompt)

    response = clean_json_response(
        response
    )

    data = json.loads(response)

    return [
        Requirement(**item)
        for item in data
    ]


# ============================================================
# Requirement Mapping
# ============================================================

def map_requirements_to_application(
    requirements,
    application_text: str
) -> list[RequirementMapping]:

    if AI_PROVIDER == "mock":

        return mock_map_requirements(
            requirements,
            application_text
        )

    requirements_text = json.dumps(
        [
            {
                "id": requirement.id,
                "requirement":
                    requirement.requirement,
                "mandatory":
                    requirement.mandatory,
                "category":
                    requirement.category,
                "source_text":
                    requirement.source_text
            }
            for requirement in requirements
        ],
        indent=2
    )

    prompt = f"""
You are reviewing a funding application
against a grant guideline.

Determine whether the application provides
evidence for EACH requirement.

IMPORTANT RULES:

1. Only use information explicitly present
   in the application.

2. NEVER invent facts or evidence.

3. Every requirement must appear exactly once.

4. Use exactly one status:

SUPPORTED
MISSING
WEAK
AMBIGUOUS

5. SUPPORTED:
The application clearly provides evidence
satisfying the requirement.

6. MISSING:
The application provides no evidence.

7. WEAK:
The application mentions the requirement
but lacks sufficient detail.

8. AMBIGUOUS:
Potentially relevant information exists,
but it is unclear whether it satisfies
the requirement.

9. For SUPPORTED, WEAK, or AMBIGUOUS:
evidence MUST contain exact text copied
from the application.

10. For MISSING:
evidence MUST be an empty array.

11. Evidence must come ONLY from
the application.

12. Do not make legal or funding
eligibility decisions.

13. Return ONLY valid JSON.

14. Return a JSON array.

Requirements:

{requirements_text}

Application:

{application_text}
"""

    response = ask_gemini(prompt)

    response = clean_json_response(
        response
    )

    data = json.loads(response)

    return [
        RequirementMapping(**item)
        for item in data
    ]


# ============================================================
# JSON cleanup
# ============================================================

def clean_json_response(
    response: str
) -> str:

    response = response.strip()

    if response.startswith("```"):

        lines = response.splitlines()

        if lines:
            lines = lines[1:]

        if lines and (
            lines[-1].strip()
            == "```"
        ):
            lines = lines[:-1]

        response = "\n".join(
            lines
        ).strip()

    return response


# ============================================================
# MOCK REQUIREMENT EXTRACTION
# ============================================================

def mock_extract_requirements(
    guideline_text: str
) -> list[Requirement]:

    return [

        Requirement(
            requirement=
                "Must be a registered non-profit organization",
            mandatory=True,
            category="eligibility",
            source_text=
                "Applicants must be registered non-profit organizations."
        ),

        Requirement(
            requirement=
                "Must have operated for at least two years",
            mandatory=True,
            category="eligibility",
            source_text=
                "Applicants must have operated for at least two years."
        ),

        Requirement(
            requirement=
                "Must provide a detailed project description",
            mandatory=True,
            category="submission",
            source_text=
                "Applicants must provide a detailed project description."
        ),

        Requirement(
            requirement=
                "Explain how the project benefits the target community",
            mandatory=False,
            category="submission",
            source_text=
                "Applicants should explain how the project benefits the target community."
        ),

        Requirement(
            requirement=
                "Must provide a detailed project budget",
            mandatory=True,
            category="budget",
            source_text=
                "Applicants must provide a detailed project budget."
        ),

        Requirement(
            requirement=
                "Provide an estimated project timeline",
            mandatory=False,
            category="timeline",
            source_text=
                "Applicants should provide an estimated project timeline."
        ),

        Requirement(
            requirement=
                "Must submit proof of non-profit registration",
            mandatory=True,
            category="supporting_document",
            source_text=
                "Applicants must submit proof of non-profit registration."
        ),

        Requirement(
            requirement=
                "Must submit the organization's latest annual report",
            mandatory=True,
            category="supporting_document",
            source_text=
                "Applicants must submit the organization's latest annual report."
        )
    ]


# ============================================================
# MOCK APPLICATION MAPPING
# ============================================================

def mock_map_requirements(
    requirements,
    application_text: str
) -> list[RequirementMapping]:

    results = []

    import re

    # Normalize application text so PDF/DOCX line breaks
    # and extra spaces do not break evidence matching.
    text = re.sub(
        r"\s+",
        " ",
        application_text
    ).strip().lower()

    for requirement in requirements:

        req = requirement.requirement.lower()

        # Normalize requirement text as well.
        req = re.sub(
            r"\s+",
            " ",
            req
        ).strip()

        evidence = []
        status = "MISSING"
        reason = "No evidence found in the application."
        confidence = 0.95

        # ---------------------------------------------
        # Non-profit
        # ---------------------------------------------

        if "registered non-profit" in req:

            phrase = (
                "ABC Community Foundation is a "
                "registered non-profit organization."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application explicitly "
                    "states that the organization "
                    "is a registered non-profit."
                )

        # ---------------------------------------------
        # Operating history
        # ---------------------------------------------

        elif "operated for at least two years" in req:

            phrase = (
                "The organization has been "
                "operating since 2021."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application provides "
                    "an operating start year."
                )

        # ---------------------------------------------
        # Project description
        # ---------------------------------------------

        elif "project description" in req:

            phrase = (
                "We propose building a digital "
                "platform that helps rural "
                "communities access government services."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application describes "
                    "the proposed project."
                )

        # ---------------------------------------------
        # Community benefit
        # ---------------------------------------------

        elif "benefits the target community" in req:

            phrase = (
                "The project will benefit the target "
                "community by making important government "
                "services easier to discover and access."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application explains "
                    "the expected community benefit."
                )

        # ---------------------------------------------
        # Budget
        # ---------------------------------------------

        elif "project budget" in req:

            phrase = (
                "The total project budget is INR 10,00,000."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "WEAK"
                confidence = 0.90

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "A total budget is provided, "
                    "but no detailed cost breakdown "
                    "is included."
                )

        # ---------------------------------------------
        # Timeline
        # ---------------------------------------------

        elif "project timeline" in req:

            phrase = (
                "The project is expected to take 12 months."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application provides "
                    "an estimated project duration."
                )

        # ---------------------------------------------
        # Registration document
        # ---------------------------------------------

        elif "proof of non-profit registration" in req:

            phrase = (
                "Proof of non-profit registration is attached."
            )

            if re.sub(r"\s+", " ", phrase).strip().lower() in text:

                status = "SUPPORTED"

                evidence.append(
                    EvidenceItem(
                        source_text=phrase
                    )
                )

                reason = (
                    "The application states that "
                    "proof of registration is attached."
                )

        # ---------------------------------------------
        # Annual report
        # ---------------------------------------------

        elif "annual report" in req:

            status = "MISSING"
            confidence = 0.99

            reason = (
                "No evidence of the organization's "
                "latest annual report was found."
            )

        # ---------------------------------------------
        # Save mapping
        # ---------------------------------------------

        results.append(
            RequirementMapping(
                requirement_id=requirement.id,
                status=status,
                confidence=confidence,
                reason=reason,
                evidence=evidence
            )
        )

    return results

def generate_clarification_questions(
    requirements,
    mappings,
    application_text
):
    if AI_PROVIDER == "mock":
        return mock_generate_clarification_questions(
            requirements,
            mappings,
            application_text
        )

    requirements_text = json.dumps(
        [
            {
                "id": requirement.id,
                "requirement": requirement.requirement,
                "mandatory": requirement.mandatory,
                "category": requirement.category
            }
            for requirement in requirements
        ],
        indent=2
    )

    mappings_text = json.dumps(
        [
            {
                "requirement_id": mapping.requirement_id,
                "status": mapping.status,
                "confidence": mapping.confidence,
                "reason": mapping.reason,
                "evidence": [
                    {
                        "source_text": evidence.source_text,
                        "page_number": evidence.page_number
                    }
                    for evidence in mapping.evidence
                ]
            }
            for mapping in mappings
        ],
        indent=2
    )

    prompt = f"""
You are reviewing a funding application for completeness.

Generate clarification questions only for requirements whose
evidence is MISSING, WEAK, or AMBIGUOUS.

Do not invent facts.

Each question must help the applicant provide the missing
or unclear evidence.

Requirements:
{requirements_text}

Mappings:
{mappings_text}

Application:
{application_text}

Return ONLY valid JSON in this format:

[
  {{
    "requirement_id": 123,
    "question": "Question to ask the applicant",
    "reason": "Why clarification is needed"
  }}
]

Rules:
- Do not generate questions for SUPPORTED requirements.
- Prioritize mandatory requirements.
- Do not make legal or funding-eligibility decisions.
- Questions must be specific and actionable.
"""

    response = ask_gemini(prompt)
    response = clean_json_response(response)

    return json.loads(response)


def mock_generate_clarification_questions(
    requirements,
    mappings,
    application_text
):
    questions = []

    for requirement, mapping in zip(requirements, mappings):

        if mapping.status == "SUPPORTED":
            continue

        if mapping.status == "MISSING":
            questions.append({
                "requirement_id": mapping.requirement_id,
                "question": (
                    f"Could you provide evidence for the requirement: "
                    f"'{requirement.requirement}'?"
                ),
                "reason": (
                    "The application does not contain supporting "
                    "evidence for this requirement."
                )
            })

        elif mapping.status == "WEAK":
            questions.append({
                "requirement_id": mapping.requirement_id,
                "question": (
                    f"Could you provide more detailed evidence for: "
                    f"'{requirement.requirement}'?"
                ),
                "reason": (
                    "The application contains some evidence, but it "
                    "may not be sufficient to fully support the requirement."
                )
            })

        elif mapping.status == "AMBIGUOUS":
            questions.append({
                "requirement_id": mapping.requirement_id,
                "question": (
                    f"Could you clarify how the application satisfies: "
                    f"'{requirement.requirement}'?"
                ),
                "reason": (
                    "The available evidence is ambiguous."
                )
            })

    return questions

def detect_unsupported_claims(application_text: str):
    if AI_PROVIDER == "mock":
        return mock_detect_unsupported_claims(application_text)

    prompt = f"""
You are reviewing a funding application for evidence completeness.

Identify factual claims made in the application that are NOT
supported by the supplied application text itself.

Important rules:
- Use ONLY the supplied application text.
- Do not use outside knowledge.
- Do not decide whether a claim is legally true.
- Do not call a claim unsupported merely because it sounds ambitious.
- A claim is unsupported only when the application provides no
  evidence supporting that claim.
- Ignore ordinary statements that do not require evidence.
- Return ONLY valid JSON.

Application:
{application_text}

Return:

[
  {{
    "claim_text": "Exact claim from the application",
    "reason": "Why the supplied application does not support this claim"
  }}
]
"""

    response = ask_gemini(prompt)
    response = clean_json_response(response)

    return json.loads(response)

def mock_detect_unsupported_claims(application_text: str):
    claims = []

    text = application_text.lower()

    # Example test claim.
    if "500,000" in text or "500000" in text:
        claims.append({
            "claim_text": (
                "The project will reach 500,000 users within the first year."
            ),
            "reason": (
                "The application makes this quantitative claim but "
                "does not provide supporting evidence for it."
            )
        })

    return claims