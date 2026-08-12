import { useRef, useState } from "react";
import { getAuthHeader } from "@/lib/api";

interface MicResult {
  transcript: string;
  answer: string;
  audioB64: string;
  mimeType: string;
}

interface KudosMicProps {
  conversationId: number | null;
  disabled?: boolean;
  onResult: (res: MicResult) => void;
  onError?: (msg: string) => void;
}

/**
 * KUDOS mic — hold to talk.
 *
 * Hold the button and speak; release to send. If you held long enough
 * (>= 600 ms) KUDOS replies OUT LOUD (TTS audio autoplays). A very quick tap
 * is treated as a "waiting" press and shows a hint instead of sending silence.
 */
export default function KudosMic({ conversationId, disabled, onResult, onError }: KudosMicProps) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const pressedAtRef = useRef(0);
  const longPressRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError?.("Microphone not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch {
      onError?.("Microphone unavailable — check browser permissions.");
    }
  };

  const handleDown = () => {
    if (disabled || busy) return;
    longPressRef.current = false;
    pressedAtRef.current = Date.now();
    timerRef.current = window.setTimeout(() => {
      longPressRef.current = true;
    }, 600);
    startRecording();
  };

  const handleUp = async () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const rec = recorderRef.current;
    if (!rec || rec.state !== "recording") return;
    const duration = Date.now() - pressedAtRef.current;

    const audio = await new Promise<Blob>((resolve) => {
      rec.addEventListener("stop", () => resolve(new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" })), { once: true });
      rec.stop();
    });
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setRecording(false);

    const speak = longPressRef.current;
    if (duration < 300 && !speak) {
      onError?.("Hold the mic to talk — or tap when already recording to stop and send.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", audio, "kudos_mic.webm");
      form.append("conversation_id", String(conversationId || 0));
      form.append("text", "");
      const res = await fetch("/api/v1/kudos/voice/chat", {
        method: "POST",
        headers: getAuthHeader(),
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "KUDOS couldn't understand the audio.");
      onResult({
        transcript: data.transcript || "",
        answer: data.answer || "",
        audioB64: speak ? data.audio_b64 || "" : "",
        mimeType: data.mime_type || "audio/mpeg",
      });
    } catch (e: any) {
      onError?.(e.message || "Voice request failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleLeave = () => {
    if (recording) handleUp();
  };

  return (
    <button
      type="button"
      onPointerDown={handleDown}
      onPointerUp={handleUp}
      onPointerLeave={handleLeave}
      onPointerCancel={handleLeave}
      disabled={disabled || busy}
      title={recording ? "Release to send" : "Hold to talk — hold longer for KUDOS to speak back"}
      className={`rounded-full w-12 h-12 flex items-center justify-center text-xl shrink-0 transition select-none touch-none ${
        busy
          ? "bg-gray-200 text-gray-500"
          : recording
            ? "bg-red-500 text-white animate-pulse"
            : "bg-amber-600 text-white hover:bg-amber-700"
      } disabled:opacity-50`}
    >
      {busy ? "…" : "🎤"}
    </button>
  );
}