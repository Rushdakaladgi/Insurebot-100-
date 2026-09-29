"""
backend/app/ai/chatbot.py
Insurance chatbot using Groq API (openai/gpt-oss-20b)
"""

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

MODEL = "openai/gpt-oss-20b"
MAX_HISTORY = 8            # only last N messages sent -> saves input tokens
SHORT_TOKENS = 500         # normal answers (includes reasoning tokens)
DETAILED_TOKENS = 1500     # when user asks for detail / steps / lists

DETAIL_KEYWORDS = [
    "detail", "explain", "step by step", "steps", "in depth", "elaborate",
    "full process", "complete guide", "list all", "everything about", "how to file",
]

SYSTEM_PROMPT = """You are InsureBot, an AI assistant for an Indian insurance claims platform.

You help with: health/car/house/business policies, filing claims in India, IRDAI rules,
required documents, policy terms and exclusions, settlement timelines, avoiding claim rejection.

Rules:
- Use Indian context (₹, IRDAI, Indian practices).
- Be empathetic when users are dealing with damage or loss.
- If you lack policy specifics, ask the user to upload their policy document.
- Never give legal or financial advice; suggest a professional for complex cases.

Length rules (important):
- Default: answer in 2-5 short sentences or up to 5 tight bullets (about 60-120 words).
- Give the direct answer first, no long intros, no repeating the question.
- Only go longer (up to ~350 words) if the user asks for detail, steps, or a full explanation.
- Always finish your last sentence; if there is more to say, end with a one-line offer to continue."""


def _wants_detail(text: str) -> bool:
    text = text.lower()
    return any(k in text for k in DETAIL_KEYWORDS)


def chat(messages: list) -> str:
    """
    messages: list of {role: user/assistant, content: str}
    Returns: response string
    """
    if not GROQ_API_KEY:
        return _fallback_response(messages)

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)

        # Keep only recent, valid messages
        recent = [m for m in messages if m["role"] in ("user", "assistant")][-MAX_HISTORY:]
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + recent

        last_user = recent[-1]["content"] if recent else ""
        budget = DETAILED_TOKENS if _wants_detail(last_user) else SHORT_TOKENS

        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            max_completion_tokens=budget,
            reasoning_effort="low",   # fewer hidden thinking tokens
            temperature=0.5,
        )

        choice = response.choices[0]
        text = (choice.message.content or "").strip()

        if not text:  # reasoning ate the whole budget
            return "Sorry, I couldn't finish that answer. Could you rephrase or ask a more specific question?"

        if choice.finish_reason == "length":
            text += "\n\n_(Reply was cut short — type **continue** for the rest.)_"

        return text

    except Exception as e:
        print(f"[Chatbot Error] {e}")
        return _fallback_response(messages)


def _fallback_response(messages: list) -> str:
    last = messages[-1]["content"].lower() if messages else ""

    if any(word in last for word in ["hello", "hi", "hey"]):
        return "Hello! I'm InsureBot, your insurance assistant. How can I help you today?"
    if "claim" in last:
        return "To file a claim, you'll need your policy number, incident details, photos of damage, and relevant documents like FIR copy or medical bills. Would you like guidance for a specific claim type?"
    if "document" in last:
        return "Common documents required: Policy document, Photo ID, Incident report/FIR, Photos of damage, Repair estimates. The exact list depends on your claim type."
    if "reject" in last:
        return "Claims are commonly rejected due to: policy lapse, delayed reporting, incomplete documents, pre-existing conditions (health), or driving violations (car). Would you like tips to avoid rejection?"

    return "I'm here to help with your insurance questions. You can ask me about filing claims, required documents, policy coverage, or IRDAI regulations."
