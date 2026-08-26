import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Voice input, built entirely on browser-native APIs — no backend round
 * trip, no API key, works offline-of-our-servers. Two browser APIs do
 * different jobs and are wired together here:
 *
 *   - SpeechRecognition: turns audio into text (interim + final).
 *   - Web Audio's AnalyserNode: reads live mic volume so the UI can
 *     render a waveform that actually reacts to the user's voice,
 *     instead of a canned pulse animation.
 *
 * SpeechRecognition alone doesn't expose audio levels, hence running
 * both a recognizer AND a getUserMedia() stream simultaneously.
 */

type VoiceState = 'idle' | 'listening' | 'processing' | 'error';

export interface UseVoiceInputResult {
  supported: boolean;
  state: VoiceState;
  transcript: string;
  interimTranscript: string;
  level: number; // 0..1, smoothed mic volume — drives the waveform
  start: () => void;
  stop: () => void;
  error: string | null;
}

const SILENCE_STOP_MS = 1800;

export function useVoiceInput(onFinalTranscript?: (text: string) => void): UseVoiceInputResult {
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finalRef = useRef('');
  const onFinalRef = useRef(onFinalTranscript);
  onFinalRef.current = onFinalTranscript;

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setSupported(!!SR && !!navigator.mediaDevices?.getUserMedia);
  }, []);

  const teardownAudio = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setLevel(0);
  }, []);

  const stop = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    try {
      recognitionRef.current?.stop();
    } catch (_) {
      /* already stopped */
    }
    teardownAudio();
    setState('idle');
    setInterimTranscript('');
  }, [teardownAudio]);

  const startAudioMeter = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext;
      const ctx: AudioContext = new AudioCtx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        const avg = sum / data.length / 255; // 0..1
        setLevel((prev) => prev * 0.6 + avg * 0.4);
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (_) {
      // Mic-level metering is cosmetic — recognition still works without it.
    }
  }, []);

  const start = useCallback(() => {
    if (!supported || state === 'listening') return;
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    finalRef.current = '';

    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    const resetSilenceTimer = () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = setTimeout(() => {
        if (finalRef.current.trim()) {
          rec.stop();
        }
      }, SILENCE_STOP_MS);
    };

    rec.onresult = (event: any) => {
      let interim = '';
      let final = finalRef.current;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += chunk + ' ';
        else interim += chunk;
      }
      finalRef.current = final;
      setTranscript(final);
      setInterimTranscript(interim);
      resetSilenceTimer();
    };

    rec.onerror = (event: any) => {
      setError(event?.error === 'not-allowed' ? 'Microphone access denied' : 'Voice input error');
      setState('error');
      teardownAudio();
    };

    rec.onend = () => {
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      teardownAudio();
      const finalText = finalRef.current.trim();
      setState('idle');
      setInterimTranscript('');
      if (finalText) onFinalRef.current?.(finalText);
    };

    recognitionRef.current = rec;
    try {
      rec.start();
      setState('listening');
      startAudioMeter();
      resetSilenceTimer();
    } catch (_) {
      setError('Could not start voice input');
      setState('error');
    }
  }, [supported, state, startAudioMeter, teardownAudio]);

  useEffect(() => () => stop(), [stop]);

  return { supported, state, transcript, interimTranscript, level, start, stop, error };
}

/**
 * Text-to-speech via the browser's built-in SpeechSynthesis — reads AI
 * replies aloud. Picks the most natural-sounding available voice once
 * (voice lists load async in Chrome) and caches it.
 */
export function useTextToSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    const pick = () => {
      const voices = window.speechSynthesis.getVoices();
      voiceRef.current =
        voices.find((v) => /Natural|Neural|Google US English/i.test(v.name)) ||
        voices.find((v) => v.lang === 'en-US') ||
        voices[0] ||
        null;
    };
    pick();
    window.speechSynthesis.onvoiceschanged = pick;
  }, []);

  const speak = useCallback((text: string) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    if (voiceRef.current) utter.voice = voiceRef.current;
    utter.rate = 1.02;
    utter.pitch = 1;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utter);
  }, []);

  const cancel = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
    }
  }, []);

  const supported = typeof window !== 'undefined' && !!window.speechSynthesis;

  return { speak, cancel, speaking, supported };
}
