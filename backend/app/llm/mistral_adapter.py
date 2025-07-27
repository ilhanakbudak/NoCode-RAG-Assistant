# backend/app/llm/mistral_adapter.py

import subprocess
import logging
import socket
import time
import json
from typing import Iterator, Optional
from app.config.settings import settings

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

def is_ollama_running() -> bool:
    try:
        with socket.create_connection((OLLAMA_HOST, OLLAMA_PORT), timeout=2):
            return True
    except OSError:
        return False

def start_ollama_server():
    logger.info("Ollama server not running — attempting to start it...")

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)  # give server time to boot
        if is_ollama_running():
            logger.info("✅ Ollama server started successfully")
        else:
            logger.error("❌ Failed to start Ollama server")
    except Exception as e:
        logger.exception(f"Exception while starting Ollama server: {e}")

def query_mistral(prompt: str) -> str:
    """
    Non-streaming version for backward compatibility
    """
    logger.info(f"Sending prompt to Ollama model: {settings.ollama_model}")

    if not is_ollama_running():
        start_ollama_server()

    try:
        result = subprocess.run(
            ["ollama", "run", settings.ollama_model, prompt],
            capture_output=True,
            text=True,
            timeout=60
        )

        logger.info(f"Ollama subprocess completed with return code {result.returncode}")

        if result.stderr:
            logger.warning(f"Ollama stderr:\n{result.stderr.strip()}")

        if not result.stdout.strip():
            logger.warning("Ollama returned empty response")

        response = result.stdout.strip()
        logger.debug(f"Ollama stdout (truncated):\n{response[:500]}...")
        return response

    except subprocess.TimeoutExpired:
        logger.error("Ollama subprocess timed out")
        return "[Error: LLM model timed out]"

    except Exception as e:
        logger.exception(f"Error contacting Mistral model: {str(e)}")
        return f"[Error contacting Mistral model: {str(e)}]"

def stream_mistral_response(prompt: str) -> Iterator[str]:
    """
    Stream responses from Mistral model character-by-character and yield words as they form.

    Args:
        prompt: The prompt to send to the model

    Yields:
        str: Individual words or punctuation units as they're generated
    """
    logger.info(f"Starting streaming response from Ollama model: {settings.ollama_model}")

    if not is_ollama_running():
        start_ollama_server()

        # Wait a bit more to ensure server is ready
        if not is_ollama_running():
            yield "[Error: Ollama server not available]"
            return

    try:
        process = subprocess.Popen(
            ["ollama", "run", settings.ollama_model, prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        logger.info("Ollama streaming process started")

        full_response = ""
        current_token = ""

        while True:
            char = process.stdout.read(1)

            if not char:
                if process.poll() is not None:
                    break
                continue

            full_response += char
            current_token += char

            if char in [' ', '\n', '.', ',', '!', '?', ';', ':']:
                if current_token.strip():
                    yield current_token
                current_token = ""
                time.sleep(0.05)

        if current_token.strip():
            yield current_token

        return_code = process.wait(timeout=10)
        if return_code != 0:
            stderr_output = process.stderr.read()
            logger.error(f"Ollama process failed with return code {return_code}: {stderr_output}")
            yield f"[Error: Process failed - {stderr_output[:100]}]"
        else:
            logger.info(f"Streaming completed successfully. Total response length: {len(full_response)}")

    except subprocess.TimeoutExpired:
        logger.error("Ollama streaming process timed out")
        process.kill()
        yield "[Error: Streaming timeout]"

    except Exception as e:
        logger.exception(f"Error during streaming: {e}")
        yield f"[Error during streaming: {str(e)}]"


def stream_mistral_response_buffered(prompt: str, buffer_size: int = 3) -> Iterator[str]:
    """
    Stream responses with word buffering for better readability
    
    Args:
        prompt: The prompt to send to the model
        buffer_size: Number of words to buffer before yielding
        
    Yields:
        str: Buffered chunks of words
    """
    logger.info(f"Starting buffered streaming response (buffer_size={buffer_size})")
    
    word_buffer = []
    
    try:
        for word in stream_mistral_response(prompt):
            # Handle error messages immediately
            if word.startswith("[Error"):
                if word_buffer:
                    yield " ".join(word_buffer)
                    word_buffer = []
                yield word
                return
            
            word_buffer.append(word.strip())
            
            # Yield when buffer is full or at sentence endings
            if (len(word_buffer) >= buffer_size or 
                any(word.rstrip().endswith(punct) for punct in ['.', '!', '?'])):
                
                chunk = " ".join(word_buffer).strip()
                if chunk:
                    yield chunk + " "
                word_buffer = []
        
        # Yield any remaining words in buffer
        if word_buffer:
            chunk = " ".join(word_buffer).strip()
            if chunk:
                yield chunk
                
    except Exception as e:
        logger.exception(f"Error in buffered streaming: {e}")
        if word_buffer:
            yield " ".join(word_buffer)
        yield f"[Error in buffered streaming: {str(e)}]"

def test_streaming() -> None:
    """
    Test function to verify streaming works correctly
    """
    logger.info("Testing streaming functionality...")
    
    test_prompt = "Explain what artificial intelligence is in simple terms."
    
    print("Testing word-by-word streaming:")
    for word in stream_mistral_response(test_prompt):
        print(word, end='', flush=True)
    
    print("\n\nTesting buffered streaming:")
    for chunk in stream_mistral_response_buffered(test_prompt, buffer_size=2):
        print(chunk, end='', flush=True)
    
    print("\n\nStreaming test completed.")

# Backwards compatibility - keep the original function name
query_mistral_stream = stream_mistral_response