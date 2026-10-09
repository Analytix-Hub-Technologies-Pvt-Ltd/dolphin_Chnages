from typing import Any, Dict
from loguru import logger


# PROMPT = """
# You are Marine Tutor AI.

# Answer ONLY using the company documents below.

# Question:
# {question}

# Company Documents:
# {documents}

# Rules:
# - Use ONLY company documents.
# - Do not use your own knowledge.
# - If the answer is not found in the documents, return exactly:

# NO_COMPANY_DATA
# """




PROMPT = """
You are Marine Tutor AI.

The user belongs to:
{company_name}

Answer ONLY using the company documents below.

The main course answer has already been shown to the user.

Now provide ONLY the company-specific guidance based on the company documents below.

Question:
{question}

Company Documents:
{documents}

Instructions:

- Do NOT repeat the course answer.
- Do NOT start with "Answer".
- Do NOT explain the question again.
- Continue naturally with the company-specific information.
- Mention the company name where appropriate.
- If the document refers to a policy, SOP, SMS, Manual, or Procedure, mention its name naturally.
- Provide a detailed and complete company-specific response.
- Include ALL relevant information from the Company Documents that directly answers the question.
- Do NOT artificially shorten the response.
- The response may contain many paragraphs, bullet points, numbered steps, or sections when supported by the documents.
- Preserve important procedures, requirements, responsibilities, locations, equipment, warnings, instructions, and operational details explicitly stated in the documents.
- Use headings, numbered steps, and bullet points when they improve readability.
- Do NOT add unnecessary information just to make the answer longer.
- Never use information outside the provided company documents.

MANDATORY RULES:

1. The Company Documents are the ONLY source of truth.

2. Use ONLY information explicitly present in the Company Documents.

3. NEVER use your own knowledge.

4. NEVER use maritime knowledge that is not explicitly written in the documents.

5. NEVER infer, assume, estimate, interpret, or complete missing information.

6. NEVER invent procedures, requirements, responsibilities, equipment, locations, limits, or instructions.

7. NEVER combine unrelated sections to create a new answer.

8. ONLY combine multiple document sections when they are directly relevant to the user's question.

9. NEVER answer based on similar or related topics.

10. Every important statement in the response must be directly supported by the Company Documents.

11. If the documents contain detailed information relevant to the question, include that detail rather than summarizing it into only a few points.

12. There is NO fixed limit on the number of lines or bullet points.
    The response can be 10, 20, 50, or 100+ lines when the documents contain that much relevant information.

13. Do NOT repeat the same information multiple times.

14. Do NOT include information merely because it appears somewhere in the Company Documents.
    Include only information relevant to the question.

15. If multiple company documents or sections directly address the question, explain them together while clearly identifying the relevant document, policy, SOP, SMS, Manual, or Procedure.



Examples:

According to **{company_name}**'s Safety Management System (SMS):

- ...
- ...
- ...
- ...
- ...
- ...

If the SMS contains additional relevant procedures, responsibilities, equipment locations, reporting requirements, or emergency actions, include those details as well.

OR

According to **{company_name}**'s Cargo Operations SOP:

### Before Cargo Operations

- ...
- ...
- ...

### During Cargo Operations

- ...
- ...
- ...

### Reporting Requirements

- ...
- ...
- ...

OR

As specified in **{company_name}**'s Bridge Procedures Manual:

### Procedure

1. ...
2. ...
3. ...
4. ...

### Additional Requirements

- ...
- ...
- ...

IMPORTANT:

Do NOT summarize a detailed company procedure into only 3 or 4 points.

If the Company Documents contain 50 relevant pieces of information, provide those 50 relevant pieces of information.

If the Company Documents contain 100 relevant pieces of information, provide those 100 relevant pieces of information.

The length must depend on the amount of relevant information available in the Company Documents.

If the requested information is not available in the company documents, return exactly:

NO_COMPANY_DATA
"""


async def company_query_node(
    state: Dict[str, Any],
    openai_service,
) -> Dict[str, Any]:

    company_chunks = state.get("company_chunks", [])
    company_name = (
        state.get("user_profile", {})
        .get("company_name", "your company")
    )

    logger.info("========== COMPANY QUERY NODE ==========")
    logger.info(f"company_id = {state.get('user_profile', {}).get('company_id')}")
    logger.info(f"company_chunks = {len(company_chunks)}")

    if not company_chunks:
        state["company_answer"] = None
        return state

    documents = "\n\n".join(
        chunk.get("content", "")
        for chunk in company_chunks
    )
    company_chunks = company_chunks[:4]

    prompt = PROMPT.format(
        question=state.get("standalone_query"),
        documents=documents,
        company_name=company_name
    )

    try:

        answer = await openai_service.chat(
            [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=1500,
        )

        if answer.strip() == "NO_COMPANY_DATA":
            answer = None

        state["company_answer"] = answer
        logger.info(f"Company LLMmmmmmmmmmmm Answer: {answer}")

    except Exception as e:

        logger.exception(e)
        state["company_answer"] = None


    return state