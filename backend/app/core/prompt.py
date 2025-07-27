# backend/app/core/prompt.py

import re
import logging

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def sanitize_user_input(text: str) -> str:
    logger.debug(f"Sanitizing user input: {text}")
    
    text = text.strip()
    text = re.sub(r"[{}\[\]<>]", "", text)  # Remove common injection characters
    text = re.sub(r"\s+", " ", text)        # Collapse excessive whitespace

    sanitized = text[:1000]  # Optional limit for safety
    logger.info(f"Sanitized input (length {len(sanitized)}): {sanitized}")
    return sanitized

def build_prompt(context: str, user_input: str) -> str:
    logger.info("Building prompt...")
    
    user_input = sanitize_user_input(user_input)

    if not context.strip():
        logger.warning("Context is empty or whitespace only")

    prompt = f"""
You are a professional, friendly, and concise customer support agent.

Here is company context you MUST use when answering:
-----------------------
{context}
-----------------------

Here is the user's message:
"{user_input}"

Answer clearly using ONLY the context provided. If you're unsure, respond:
"I'm not sure about that. Let me connect you to a support representative."
"""
    logger.debug(f"Final prompt (truncated):\n{prompt[:500]}...")  # Trim if needed
    return prompt
