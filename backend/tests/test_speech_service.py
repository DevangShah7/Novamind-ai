"""
Tests for the speech service
"""
import pytest
import asyncio
from backend.app.core.speech_service import SpeechServiceFactory, speech_to_text, text_to_speech

@pytest.mark.asyncio
async def test_speech_service_factory():
    """Test that the speech service factory creates the correct service type"""
    service = SpeechServiceFactory.create_service("whisper")
    assert isinstance(service, SpeechServiceFactory.create_service("whisper").__class__)

@pytest.mark.asyncio
async def test_speech_to_text_placeholder():
    """Test the placeholder speech-to-text function"""
    # Create some dummy audio data
    audio_data = b"dummy audio data"

    result = await speech_to_text(audio_data, language="en-US")

    # Check that we got a reasonable response
    assert isinstance(result, dict)
    assert "text" in result
    assert "language" in result
    assert "confidence" in result
    assert result["language"] == "en-US"
    assert isinstance(result["confidence"], float)
    assert 0 <= result["confidence"] <= 1

@pytest.mark.asyncio
async def test_text_to_speech_placeholder():
    """Test the placeholder text-to-speech function"""
    text = "Hello, world!"

    audio_data = await text_to_speech(text, voice="default", speed=1.0, pitch=1.0)

    # Check that we got audio data back
    assert isinstance(audio_data, bytes)
    assert len(audio_data) > 0

    # Check that it's a valid WAV file (starts with RIFF)
    assert audio_data.startswith(b'RIFF')

@pytest.mark.asyncio
async def test_text_to_speech_with_parameters():
    """Test text-to-speech with different parameters"""
    text = "Test sentence"

    # Test with different speed
    audio_fast = await text_to_speech(text, speed=1.5)
    audio_slow = await text_to_speech(text, speed=0.5)

    # Both should return valid audio data
    assert isinstance(audio_fast, bytes)
    assert isinstance(audio_slow, bytes)
    assert len(audio_fast) > 0
    assert len(audio_slow) > 0

    # Test with different pitch
    audio_high_pitch = await text_to_speech(text, pitch=1.5)
    audio_low_pitch = await text_to_speech(text, pitch=0.5)

    assert isinstance(audio_high_pitch, bytes)
    assert isinstance(audio_low_pitch, bytes)
    assert len(audio_high_pitch) > 0
    assert len(audio_low_pitch) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])