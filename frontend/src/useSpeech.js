import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser speech-to-text for the mic button (Web Speech API).
 * Wispr Flow works system-wide too: focus the textarea and hold your
 * Wispr Flow hotkey - the transcription lands in the same box.
 */
export function useSpeech(onText) {
  const SR =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const supported = Boolean(SR);
  const [listening, setListening] = useState(false);
  const recRef = useRef(null);
  const cbRef = useRef(onText);
  cbRef.current = onText;

  const stop = useCallback(() => {
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    if (!SR) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }
      cbRef.current(text.trim());
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }, [SR]);

  useEffect(() => () => recRef.current?.abort(), []);

  return { supported, listening, start, stop };
}
