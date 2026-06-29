"""
Voice processing endpoints for NovaMind AI
Provides speech-to-text and text-to-speech capabilities
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import Response
from typing import Optional
import logging
from app.core.speech_service import speech_to_text, text_to_speech
from app.api.deps import get_current_active_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

@router.post("/speech-to-text")
async def speech_to_text_endpoint(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Convert speech audio to text

    Args:
        audio_file: Uploaded audio file
        language: Language code for recognition (default: en-US)
        current_user: Currently authenticated user

    Returns:
        Transcription results
    """
    try:
        # Read audio file content
        audio_data = await audio_file.read()

        # Process speech to text
        result = await speech_to_text(audio_data, language)

        logger.info(f"User {current_user.id} processed speech-to-text: {len(audio_data)} bytes")

        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Error in speech-to-text endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Speech-to-text processing failed: {str(e)}")

@router.post("/text-to-speech")
async def text_to_speech_endpoint(
    text: str = Form(...),
    voice: str = Form("default"),
    speed: float = Form(1.0),
    pitch: float = Form(1.0),
    current_user: User = Depends(get_current_active_user)
):
    """
    Convert text to speech audio

    Args:
        text: Text to convert to speech
        voice: Voice identifier to use
        speed: Speech speed (0.5 to 2.0)
        pitch: Speech pitch (0.5 to 2.0)
        current_user: Currently authenticated user

    Returns:
        Audio file response
    """
    try:
        # Validate input
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        if len(text) > 5000:  # Reasonable limit
            raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")

        # Process text to speech
        audio_bytes = await text_to_speech(text, voice, speed, pitch)

        logger.info(f"User {current_user.id} processed text-to-speech: {len(text)} characters")

        # Return audio file
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
    except Exception as e:
        logger.error(f"Error in text-to-speech endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Text-to-speech processing failed: {str(e)}")