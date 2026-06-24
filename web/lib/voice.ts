/**
 * Voice service integration functions
 * Provides speech-to-text and text-to-speech capabilities
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Speech-to-text conversion
 * @param audioFile - Audio file to convert to text
 * @param language - Language code (default: en-US)
 * @returns Promise resolving to transcription result
 */
export const speechToText = async (
  audioFile: File,
  language: string = 'en-US'
): Promise<{ text: string; language: string; confidence: number }> => {
  try {
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    formData.append('language', language);

    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const response = await fetch(`${API_URL}/voice/speech-to-text`, {
      method: 'POST',
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error(`Speech-to-text request failed: ${response.status}`);
    }

    const json = await response.json();
    return json.data;
  } catch (error) {
    console.error('Speech-to-text error:', error);
    throw new Error('Failed to convert speech to text');
  }
};

/**
 * Text-to-speech conversion
 * @param text - Text to convert to speech
 * @param voice - Voice identifier (default: default)
 * @param speed - Speech speed (0.5 to 2.0, default: 1.0)
 * @param pitch - Speech pitch (0.5 to 2.0, default: 1.0)
 * @returns Promise resolving to audio blob
 */
export const textToSpeech = async (
  text: string,
  voice: string = 'default',
  speed: number = 1.0,
  pitch: number = 1.0
): Promise<Blob> => {
  try {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('voice', voice);
    formData.append('speed', speed.toString());
    formData.append('pitch', pitch.toString());

    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const response = await fetch(`${API_URL}/voice/text-to-speech`, {
      method: 'POST',
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error(`Text-to-speech request failed: ${response.status}`);
    }

    return response.blob();
  } catch (error) {
    console.error('Text-to-speech error:', error);
    throw new Error('Failed to convert text to speech');
  }
};