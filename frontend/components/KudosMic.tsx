import { useEffect, useRef, useState } from "react";
import { getAuthHeader } from "@/lib/api";

interface MicResult {
  transcript: string;
  answer: string;
  audioB64: string;
  mimeType: string;
}

type MicVariant = "kudos" | "guest" | "transcribe";

interface KudosMicProps {
  conversationId?: number | null;
  guestId?: string;
  variant?: MicVariant;
  disabled?: boolean;
  greeting?: boolean;
  onResult?: (res: MicResult) => void;
  onTranscript?: (text: string) => void;
  onError?: (msg: string) => void;
}

/**
 * KUDOS mic — tap to toggle.
 *
 * Tap once to turn the mic ON: KUDOS greets out loud ("Go ahead, I'm
 * listening") then starts recording. Tap again to STOP and send — KUDOS
 * transcribes, answers in context of the conversation, and speaks the reply
 * back (audio autoplays).
 *
 * `variant`:
 *   - "kudos"      -> authenticated /kudos voice loop (POST /voice/chat)
 *   - "guest"      -> anonymous voice loop (POST /guest/voice/chat)
 *   - "transcribe" -> transcript-only (POST /voice/transcribe) for room chat
 */
export default function KudosMic({
  conversationId,
  guestId,
  variant = "kudos",
  disabled,
  greeting = true,
  onResult,
  onTranscript,
  onError,
}: KudosMicProps) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  const playB64 = (b64: string, mime: string) => {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const url = URL.createObjectURL(new Blob([bytes], { type: mime || "audio/mpeg" }));
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audio.play().catch(() => URL.revokeObjectURL(url));
    } catch {
      /* best-effort playback */
    }
  };

  const headers = () => getAuthHeader();

  const greet = async () => {
    if (!greeting || typeof window === "undefined") return;
    try {
      if (variant === "guest") {
        const fd = new FormData();
        fd.append("guest_id", guestId || "");
        const res = await fetch("/api/v1/kudos/guest/voice/greet", { method: "POST", body: fd });
        if (res.ok) {
          const d = await res.json();
          if (d.audio_b64) playB64(d.audio_b64, d.mime_type);
        }
      } else {
        const res = await fetch("/api/v1/kudos/voice/greet", { method: "POST", headers: headers() });
        if (res.ok) {
          const d = await res.json();
          if (d.audio_b64) playB64(d.audio_b64, d.mime_type);
        }
      }
    } catch {
      /* greeting is best-effort */
    }
  };

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
      greet();
    } catch {
      onError?.("Microphone unavailable — allow the mic (HTTPS required).");
    }
  };

  const stopRecording = async () => {
    const rec = recorderRef.current;
    if (!rec || rec.state !== "recording") return;
    const audio = await new Promise<Blob>((resolve) => {
      rec.addEventListener("stop", () => resolve(new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" })), { once: true });
      rec.stop();
    });
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setRecording(false);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", audio, "kudos_mic.webm");

      if (variant === "transcribe") {
        const res = await fetch("/api/v1/kudos/voice/transcribe", {
          method: "POST",
          headers: headers(),
          body: form,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "KUDOS couldn't understand the audio.");
        onTranscript?.(data.transcript || "");
      } else if (variant === "guest") {
        form.append("guest_id", guestId || "");
        const res = await fetch("/api/v1/kudos/guest/voice/chat", {
          method: "POST",
          body: form,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "KUDOS couldn't understand the audio.");
        onResult?.({
          transcript: data.transcript || "",
          answer: data.answer || "",
          audioB64: data.audio_b64 || "",
          mimeType: data.mime_type || "audio/mpeg",
        });
      } else {
        form.append("conversation_id", String(conversationId || 0));
        form.append("text", "");
        const res = await fetch("/api/v1/kudos/voice/chat", {
          method: "POST",
          headers: headers(),
          body: form,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "KUDOS couldn't understand the audio.");
        onResult?.({
          transcript: data.transcript || "",
          answer: data.answer || "",
          audioB64: data.audio_b64 || "",
          mimeType: data.mime_type || "audio/mpeg",
        });
      }
    } catch (e: any) {
      onError?.(e.message || "Voice request failed.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = () => {
    if (disabled || busy) return;
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled || busy}
      title={recording ? "Tap to stop and send" : "Turn the mic on — KUDOS listens and speaks back"}
      className={`rounded-full w-12 h-12 flex items-center justify-center text-xl shrink-0 transition select-none touch-none ${
        busy
          ? "bg-gray-200 text-gray-500"
          : recording
            ? "bg-red-500 text-white animate-pulse"
            : "bg-amber-600 text-white hover:bg-amber-700"
      } disabled:opacity-50`}
    >
      {busy ? "…" : recording ? "🔴" : "🎤"}
    </button>
  );
}