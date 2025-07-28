# backend/app/llm/tokenizer.py

from transformers import AutoTokenizer
import logging

logger = logging.getLogger(__name__)

# You can configure this in settings later
DEFAULT_TOKENIZER_MODEL = "bert-base-uncased"

def get_tokenizer(model_name: str = DEFAULT_TOKENIZER_MODEL):
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        logger.info(f"Tokenizer loaded: {model_name}")
        return tokenizer
    except Exception as e:
        logger.warning(f"Failed to load tokenizer {model_name}, fallback to character count: {e}")
        return None
