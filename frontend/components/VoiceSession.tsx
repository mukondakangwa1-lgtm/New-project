import { useEffect, useRef, useState } from "react";
import { getAuthHeader } from "@/lib/api";

interface SessionStatus {
  session_id: number | null;
  state: string;
  turn_count: number;
  total_seconds: number;
  target_seconds: number;
  draft_ready: boolean;
  final_ready: boolean;
}

interface TurnResult extends SessionStatus {
  transcript: string;
  echo: { audio_b64: string; mime_type: string; provider: string };
  echo_line: string;
}

/**
 * KUDOS Voice Session — the interactive way to give KUDOS your voice.
 * KUDOS greets → you speak a line → KUDOS draft-clones your audio and re-speaks
 * your exact words back in the draft of your voice. Keep going until you have
 * ~30s of clear speech, then finalize: KUDOS speaks with YOUR voice everywhere.
 */
export default function VoiceSession() {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [greeting, setGreeting] = useState("");
  const [transcript, setTranscript] = useState("");
  const [echoLine, setEchoLine] = useState("");
  const [echoUrl, setEchoUrl] = useState("");
  const [message, setMessage] = useState<{ text: string; type: string }>({ text: "", type: "" });
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const echoRef = useRef<HTMLAudioElement | null>(null);

  const auth = () => ({ headers: getAuthHeader() });

  const load = async () => {
    try {
      const res = await fetch("/api/v1/kudos/voice/session/status", auth());
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  useEffect(() => {
    load();
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const setMsg = (text: string, type = "success") => setMessage({ text, type });

  const pickMime = () => {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg", "audio/mp4", "audio/wav"];
    if (typeof MediaRecorder === "undefined") return "";
    for (const m of candidates) {
      try {
        if (MediaRecorder.isTypeSupported(m)) return m;
      } catch {}
    }
    return "";
  };

  const startSession = async () => {
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/session/start", { method: "POST", headers: auth().headers });
      if (res.ok) {
        const d = await res.json();
        setStatus(d);
        setGreeting(d.greeting || "");
        setTranscript("");
        setEchoLine("");
        setEchoUrl("");
        setMsg("👋 KUDOS is listening. Speak a line back — KUDOS will repeat it in the draft of your voice.");
      } else {
        setMsg((await res.json()).detail || "Could not start session", "error");
      }
    } catch {
      setMsg("Could not start session", "error");
    }
    setBusy(false);
  };

  const startRecord = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mime = pickMime();
      const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        sendTurn(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch {
      setMsg("Microphone access denied — allow the mic (HTTPS required)", "error");
    }
  };

  const stopRecord = () => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        sendTurn(blob);
      };
      rec.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setRecording(false);
  };

  const sendTurn = async (blob: Blob) => {
    if (blob.size < 8000) {
      setMsg("That was too short — speak for a few seconds and try again", "error");
      return;
    }
    if (!status?.session_id) {
      setMsg("Start a session first", "error");
      return;
    }
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") || blob.type.includes("aac") ? "m4a" : "webm";
    const fd = new FormData();
    fd.append("file", blob, `session_line.${ext}`);
    fd.append("session_id", String(status.session_id));
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/session/turn", { method: "POST", headers: auth().headers, body: fd });
      if (res.ok) {
        const d: TurnResult = await res.json();
        setStatus(d);
        setTranscript(d.transcript || "");
        setEchoLine(d.echo_line || "");
        setEchoUrl(d.echo.audio_b64 ? `data:${d.echo.mime_type || "audio/mpeg"};base64,${d.echo.audio_b64}` : "");
        setMsg(`🎙️ Captured — ${d.total_seconds}s of ${d.target_seconds}s target.`);
      } else {
        setMsg((await res.json()).detail || "Could not send that line", "error");
      }
    } catch {
      setMsg("Could not send that line", "error");
    }
    setBusy(false);
  };

  const finalize = async () => {
    if (!status?.session_id) return;
    if (!status.final_ready && !window.confirm("You haven't reached the target yet — finalize anyway? A shorter clone works but sounds less like you.")) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("session_id", String(status.session_id));
      const res = await fetch("/api/v1/kudos/voice/session/finalize", { method: "POST", headers: auth().headers, body: fd });
      const d = await res.json();
      if (res.ok) {
        setMsg("🎉 Signature voice is LIVE — KUDOS now speaks with your voice across every platform!");
        setStatus({ ...status, state: "finalized" });
      } else {
        setMsg(d.detail || "Could not finalize", "error");
      }
    } catch {
      setMsg("Could not finalize", "error");
    }
    setBusy(false);
  };

  const cancel = async () => {
    if (!status?.session_id) return;
    if (!window.confirm("Cancel this session? Your captured lines are kept but no signature voice is created.")) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("session_id", String(status.session_id));
      await fetch("/api/v1/kudos/voice/session/cancel", { method: "POST", headers: auth().headers, body: fd });
      setStatus(null);
      setTranscript("");
      setEchoLine("");
      setEchoUrl("");
      setMsg("Session cancelled.", "error");
    } catch {}
    setBusy(false);
  };

  const pct = status?.target_seconds ? Math.min(100, Math.round(((status.total_seconds || 0) / status.target_seconds) * 100)) : 0;
  const inProgress = !!status?.session_id && status.state === "active";

  return (
    <div className="bg-white rounded-xl border shadow p-6 mt-6">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <h3 className="font-semibold text-lg">🎙️ Interactive voice session</h3>
          <p className="text-sm text-gray-500">
            Talk to KUDOS — it repeats your words back in the draft of your voice until the signature is ready.
          </p>
        </div>
        {status && (
          <span className={`text-xs px-3 py-1 rounded-full ${status.state === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
            Session {status.state}
          </span>
        )}
      </div>

      {message.text && (
        <div className={`mb-4 p-3 rounded text-sm ${message.type === "error" ? "bg-red-50 border border-red-200 text-red-700" : "bg-green-50 border border-green-200 text-green-700"}`}>
          {message.text}
        </div>
      )}

      {!inProgress ? (
        <button
          onClick={startSession}
          disabled={busy}
          className="w-full py-3 rounded-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 transition disabled:opacity-50"
        >
          👋 Start a voice session
        </button>
      ) : (
        <div className="space-y-4">
          {greeting && <p className="text-sm bg-indigo-50 border border-indigo-100 rounded p-3 text-indigo-800">{greeting}</p>}

          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">Record your line</p>
              <p className="text-xs text-gray-400">
                {status.turn_count} line{status.turn_count === 1 ? "" : "s"} · {status.total_seconds}s of {status.target_seconds}s
              </p>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
              <div className="bg-indigo-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            {!recording ? (
              <button onClick={startRecord} disabled={busy} className="bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700 disabled:opacity-50">
                🔴 Speak a line
              </button>
            ) : (
              <button onClick={stopRecord} className="bg-gray-800 text-white px-4 py-2 rounded text-sm hover:bg-gray-900">
                ⏹ Stop
              </button>
            )}
            {recording && <p className="text-xs text-red-500 animate-pulse mt-2">Recording… speak clearly.</p>}
          </div>

          {transcript && (
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm font-medium mb-1">📝 You said</p>
              <p className="text-sm text-gray-700">{transcript}</p>
              {echoUrl && (
                <div className="mt-3">
                  <p className="text-sm font-medium mb-1">🔁 KUDOS says it back in your voice</p>
                  <audio ref={echoRef} src={echoUrl} controls className="w-full" />
                </div>
              )}
              <p className="text-xs text-gray-400 mt-2">{echoLine}</p>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={startRecord}
              disabled={busy || recording}
              className="bg-gray-800 text-white px-4 py-2 rounded text-sm hover:bg-gray-900 disabled:opacity-50"
            >
              🔁 Another line
            </button>
            <button
              onClick={finalize}
              disabled={busy}
              className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 disabled:opacity-50"
            >
              ✅ It&apos;s perfect — make it KUDOS&apos;s voice
            </button>
            <button onClick={cancel} disabled={busy} className="bg-white border px-4 py-2 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
              ✕ Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
