# backend/app/routes/chat.py

import logging
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ingest.retriever import retrieve_context
from app.core.prompt import build_prompt
from app.llm.mistral_adapter import query_mistral, stream_mistral_response_buffered

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

chat_router = APIRouter()                                                                                                                                                                                                                                                                                                                                                                                                        

class ChatRequest(BaseModel):
    message: str
    company_id: str
    stream: bool = False

class StreamingChatRequest(BaseModel):
    message: str
    company_id: str

def format_sse_message(data: str, event_type: str = "message") -> str:
    """
    Format message for Server-Sent Events
    
    Args:
        data: The data to send
        event_type: Type of event (message, error, done)
        
    Returns:
        Formatted SSE string
    """
    # Escape newlines in data for SSE format
    cleaned_data = data.replace('\n', '\\n').replace('\r', '\\r')
    
    return f"event: {event_type}\ndata: {cleaned_data}\n\n"

def format_sse_json(data: dict, event_type: str = "message") -> str:
    """
    Format JSON data for Server-Sent Events
    
    Args:
        data: Dictionary to send as JSON
        event_type: Type of event
        
    Returns:
        Formatted SSE string
    """
    json_data = json.dumps(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"

async def generate_streaming_response(message: str, company_id: str):
    """
    Generator function for streaming chat responses
    
    Args:
        message: User message
        company_id: Company identifier
        
    Yields:
        SSE formatted strings
    """
    logger.info(f"Starting streaming response | Company: {company_id} | Message: {message}")
    
    try:
        # Send initial status
        yield format_sse_json({
            "type": "status",
            "message": "Processing your request...",
            "stage": "retrieving_context"
        }, "status")
        
        # ---------------------------
        # Retrieve Relevant Context
        # ---------------------------
        context = retrieve_context(message, company_id)
        if not context:
            logger.warning(f"No context found for company '{company_id}' and message: '{message}'")
            yield format_sse_json({
                "type": "warning",
                "message": "No relevant context found for this query."
            }, "warning")
            
            # Continue with a generic response
            context = "No specific context available."
        
        logger.info(f"Retrieved context (length: {len(context)} characters)")
        
        # Send context retrieved status
        yield format_sse_json({
            "type": "status", 
            "message": "Context retrieved, generating response...",
            "stage": "generating_response",
            "context_length": len(context)
        }, "status")
        
        # ---------------------------
        # Build Prompt
        # ---------------------------
        prompt = build_prompt(context, message)
        logger.debug(f"Generated prompt:\n{prompt[:1000]}...")
        logger.info("Prompt successfully generated")
        
        # Send response start indicator
        yield format_sse_json({
            "type": "response_start",
            "message": "AI is responding..."
        }, "response_start")
        
        # ---------------------------
        # Stream Language Model Response
        # ---------------------------
        full_response = ""
        chunk_count = 0
        
        try:
            for chunk in stream_mistral_response_buffered(prompt, buffer_size=3):
                if chunk.strip():
                    full_response += chunk
                    chunk_count += 1
                    
                    # Send the chunk
                    yield format_sse_json({
                        "type": "chunk",
                        "content": chunk,
                        "chunk_id": chunk_count
                    }, "chunk")
                    
                    # Add small delay to prevent overwhelming the client
                    await asyncio.sleep(0.02)
            
            logger.info(f"Streaming completed | Chunks sent: {chunk_count} | Response length: {len(full_response)}")
            
        except Exception as e:
            logger.exception(f"Error during LLM streaming: {e}")
            yield format_sse_json({
                "type": "error",
                "message": f"Error generating response: {str(e)}"
            }, "error")
            return
        
        # ---------------------------
        # Send completion status
        # ---------------------------
        yield format_sse_json({
            "type": "response_complete",
            "message": "Response completed",
            "full_response": full_response.strip(),
            "chunk_count": chunk_count,
            "word_count": len(full_response.split())
        }, "response_complete")
        
        # Final done event
        yield format_sse_message("DONE", "done")
        
    except Exception as e:
        logger.exception(f"Streaming chat handling failed: {e}")
        yield format_sse_json({
            "type": "error",
            "message": f"Internal error: {str(e)}"
        }, "error")
        yield format_sse_message("ERROR", "done")

@chat_router.post("/")
async def chat(req: ChatRequest):
    """
    Enhanced chat endpoint with optional streaming support
    """
    logger.info(f"Received chat request | Company: {req.company_id} | Message: {req.message} | Stream: {req.stream}")

    # If streaming is requested, redirect to streaming endpoint
    if req.stream:
        return StreamingResponse(
            generate_streaming_response(req.message, req.company_id),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )

    # Original non-streaming implementation for backward compatibility
    try:
        # ---------------------------
        # Retrieve Relevant Context
        # ---------------------------
        context = retrieve_context(req.message, req.company_id)
        if not context:
            logger.warning(f"No context found for company '{req.company_id}' and message: '{req.message}'")
            return {"response": "⚠️ No relevant context found for this query."}
        
        logger.info(f"Retrieved context (length: {len(context)} characters)")

        # ---------------------------
        # Build Prompt
        # ---------------------------
        prompt = build_prompt(context, req.message)
        logger.debug(f"Generated prompt:\n{prompt[:1000]}...")
        logger.info("Prompt successfully generated")

        # ---------------------------
        # Query Language Model (Non-streaming)
        # ---------------------------
        response = query_mistral(prompt)
        if not response:
            logger.warning("LLM returned no response")
            return {"response": "⚠️ No response returned from the LLM."}

        logger.info("LLM responded successfully")
        return {"response": response}

    except Exception as e:
        logger.exception(f"Chat handling failed: {e}")
        return {"response": f"⚠️ Internal error: {str(e)}"}

@chat_router.post("/stream")
async def chat_stream(req: StreamingChatRequest):
    """
    Dedicated streaming chat endpoint
    """
    logger.info(f"Received streaming chat request | Company: {req.company_id} | Message: {req.message}")
    
    return StreamingResponse(
        generate_streaming_response(req.message, req.company_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@chat_router.get("/test-stream")
async def test_streaming():
    """
    Test endpoint for streaming functionality
    """
    async def test_generator():
        for i in range(10):
            yield format_sse_json({
                "type": "test",
                "message": f"Test message {i+1}",
                "timestamp": str(asyncio.get_event_loop().time())
            }, "test")
            await asyncio.sleep(1)
        
        yield format_sse_message("DONE", "done")
    
    return StreamingResponse(
        test_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )