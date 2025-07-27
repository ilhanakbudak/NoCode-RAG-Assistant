# backend/app/main.py

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chat import chat_router
from app.routes.upload import upload_router

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------
# Environment Configuration
# ---------------------------
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logger.info("Set TOKENIZERS_PARALLELISM to 'false'")

# ---------------------------
# FastAPI App Initialization
# ---------------------------
try:
    app = FastAPI(title="AI Support Assistant")
    logger.info("FastAPI application initialized")

    # ---------------------------
    # CORS Middleware Setup
    # ---------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS middleware configured to allow all origins, methods, and headers")

    # ---------------------------
    # Router Registration
    # ---------------------------
    app.include_router(chat_router, prefix="/chat", tags=["Chat"])
    logger.info("Chat router registered at /chat")

    app.include_router(upload_router, prefix="/upload", tags=["Upload"])
    logger.info("Upload router registered at /upload")

except Exception as e:
    logger.exception(f"Error during app initialization: {e}")
    raise
