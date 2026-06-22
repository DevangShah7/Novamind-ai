/**
 * Voice service integration functions
 * Provides speech-to-text and text-to-speech capabilities
 */

import { api } from './api';

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

    const response = await api.post('/voice/speech-to-text', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data.data;
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

    const response = await api.post('/voice/text-to-speech', formData, {
      responseType: 'blob',
    });

    return new Blob([response.data], { type: 'audio/wav' });
  } catch (error) {
    console.error('Text-to-speech error:', error);
    throw new Error('Failed to convert text to speech');
  }
};