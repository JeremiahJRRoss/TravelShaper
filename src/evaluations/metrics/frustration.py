"""User frustration evaluation metric.

Used by evaluations/run_evals.py to classify TravelShaper traces as
'frustrated' or 'not_frustrated' via Phoenix llm_classify.
"""

USER_FRUSTRATION_PROMPT = """\
You are evaluating an AI travel assistant's response for signs of user frustration.

Given the user's message and the assistant's response, determine whether the user \
would likely be frustrated with the response.

A response IS frustrating if any of the following are true:
- The user asked about flights but the response contains no flight information
- The user asked about hotels but the response contains no hotel information
- The user asked about a specific destination but the response is generic and not destination-specific
- The response says "I cannot help with that" or refuses to act when the request is reasonable
- The response contains obviously fabricated specifics (fake hotel names, made-up prices) not from tool results
- The response ignores a key part of the user's request (e.g., user asked for budget options but got luxury only)
- The response is extremely short or vague when the user asked a detailed question

A response is NOT frustrating if:
- It provides useful partial information and acknowledges what it couldn't find
- It addresses the main request even if some details are missing
- It asks a reasonable clarifying question when the input is truly ambiguous

User message: {input}

Assistant response: {output}

Tool calls made: {tool_calls}

Respond with ONLY a JSON object:
{{"label": "frustrated" or "not_frustrated", "score": 0 or 1, "explanation": "One sentence explaining your judgment."}}
"""
