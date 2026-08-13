import { useEffect, useRef, useState } from "react";
import { getAuthHeader } from "@/lib/api";
import VoiceSession from "./VoiceSession";

interface VoiceStatus {
  tts_enabled: boolean;
  signature_active: boolean;
  has_cloned_voice: boolean;
  default_voice: string;
  sample_count: number;
  can_manage: boolean;
  providers: { elevenlabs: boolean; openai: boolean; coqui: boolean };
}

interface Sample {
  id: number;
  mime: string;
  transcribed: string;
  duration_seconds: number;
  created_at: string | null;
}

/**
 * KUDOS Voice — superadmin setup. Turn on KUDOS speech, record the superadmin's
 * own voice (with calibration scripts KUDOS writes), and clone it as KUDOS's
 * signature voice that speaks across every platform.
 */
export default function VoiceAdmin() {
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [script, setScript] = useState("");
  const [message, setMessage] = useState<{ text: string; type: string }>({ text: "", type: "" });
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [focus, setFocus] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const auth = () => ({ headers: getAuthHeader() });

  const load = async () => {
    try {
      const res = await fetch("/api/v1/kudos/voice/status", auth());
      if (res.ok) setStatus(await res.json());
    } catch {}
    try {
      const res = await fetch("/api/v1/kudos/voice/samples", auth());
      if (res.ok) setSamples((await res.json()).samples || []);
    } catch {}
  };

  useEffect(() => {
    load();
    return () => stopTracks(streamRef.current);
  }, []);

  const stopTracks = (stream: MediaStream | null) => {
    stream?.getTracks().forEach((t) => t.stop());
  };

  const setMsg = (text: string, type = "success") => setMessage({ text, type });

  const toggle = async () => {
    if (!status) return;
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth().headers },
        body: JSON.stringify({ enabled: !status.tts_enabled }),
      });
      if (res.ok) {
        setStatus(await res.json());
        setMsg(status.tts_enabled ? "🔇 KUDOS speech turned off" : "🎙️ KUDOS speech turned on — KUDOS now talks!");
      }
    } catch {
      setMsg("Could not toggle speech", "error");
    }
    setBusy(false);
  };

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
        uploadBlob(blob);
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
        uploadBlob(blob);
      };
      rec.stop();
    }
    stopTracks(streamRef.current);
    setRecording(false);
  };

  const uploadBlob = async (blob: Blob) => {
    if (blob.size < 8000) {
      setMsg("Recording too short — speak for a few seconds and try again", "error");
      return;
    }
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") || blob.type.includes("aac") ? "m4a" : "webm";
    const fd = new FormData();
    fd.append("file", blob, `voice_sample.${ext}`);
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/sample", { method: "POST", headers: auth().headers, body: fd });
      if (res.ok) {
        setMsg("✅ Voice sample captured — keep going! 2-3 minutes of clear speech gives the best clone.");
        await load();
      } else {
        setMsg("Could not upload sample", "error");
      }
    } catch {
      setMsg("Could not upload sample", "error");
    }
    setBusy(false);
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadBlob(file);
    e.target.value = "";
  };

  const generateScript = async () => {
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/script", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth().headers },
        body: JSON.stringify({ focus }),
      });
      if (res.ok) {
        const d = await res.json();
        setScript(d.script);
        setMsg("📜 Script ready — read it aloud and record it so KUDOS learns your pronunciations.");
      } else {
        setMsg("Could not generate script", "error");
      }
    } catch {
      setMsg("Could not generate script", "error");
    }
    setBusy(false);
  };

  const clone = async () => {
    if (!status || status.sample_count === 0) {
      setMsg("Record at least one voice sample before cloning", "error");
      return;
    }
    if (!window.confirm("Clone KUDOS's signature voice from your samples? This makes KUDOS speak with YOUR voice everywhere.")) return;
    setBusy(true);
    try {
      const res = await fetch("/api/v1/kudos/voice/clone", { method: "POST", headers: auth().headers });
      const d = await res.json();
      if (res.ok) {
        setMsg("🎙️ Signature voice is READY — KUDOS now speaks with your voice across all platforms.");
        setStatus(d);
      } else {
        setMsg(d.detail || "Clone failed", "error");
      }
    } catch {
      setMsg("Clone failed", "error");
    }
    setBusy(false);
  };

  const copyScript = () => {
    navigator.clipboard?.writeText(script).then(() => setMsg("📋 Script copied"));
  };

  return (
    <div className="bg-white rounded-xl border shadow p-6 mt-8">
      <VoiceSession />
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <h3 className="font-semibold text-lg">🎙️ KUDOS Voice — signature voice</h3>
          <p className="text-sm text-gray-500">
            KUDOS listens to <strong>your</strong> voice and speaks with it across every platform.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-3 py-1 rounded-full ${status?.tts_enabled ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
            {status?.tts_enabled ? "KUDOS speech ON" : "KUDOS speech OFF"}
          </span>
          {status?.signature_active && (
            <span className="text-xs px-3 py-1 rounded-full bg-purple-100 text-purple-700">Signature voice active</span>
          )}
        </div>
      </div>

      {message.text && (
        <div className={`mb-4 p-3 rounded text-sm ${message.type === "error" ? "bg-red-50 border border-red-200 text-red-700" : "bg-green-50 border border-green-200 text-green-700"}`}>
          {message.text}
        </div>
      )}

      {status && !status.providers.elevenlabs && !status.providers.openai && !status.providers.coqui && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
          No TTS provider configured yet. The local Coqui voice is offline — add an OpenAI key (LLM panel) for instant
          speech, or an ElevenLabs key (ELEVENLABS_API_KEY) to enable cloud cloning.
        </div>
      )}
      {status && status.providers.coqui && (
        <div className="mb-4 p-3 bg-indigo-50 border border-indigo-200 rounded text-sm text-indigo-800">
          🐸 Local Coqui voice is online — you can clone your signature voice entirely on this server, no API key needed.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: toggle + samples */}
        <div className="space-y-4">
          <button
            onClick={toggle}
            disabled={busy}
            className={`w-full py-3 rounded-lg font-medium text-white transition disabled:opacity-50 ${
              status?.tts_enabled ? "bg-red-600 hover:bg-red-700" : "bg-green-600 hover:bg-green-700"
            }`}
          >
            {status?.tts_enabled ? "🔇 Turn OFF KUDOS speech" : "🎙️ Turn ON KUDOS speech"}
          </button>

          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm font-medium mb-3">Record your voice samples</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {!recording ? (
                <button onClick={startRecord} disabled={busy} className="bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700 disabled:opacity-50">
                  🔴 Record
                </button>
              ) : (
                <button onClick={stopRecord} className="bg-gray-800 text-white px-4 py-2 rounded text-sm hover:bg-gray-900">
                  ⏹ Stop
                </button>
              )}
              <label className="bg-white border px-4 py-2 rounded text-sm hover:bg-gray-50 cursor-pointer">
                📁 Upload audio file
                <input type="file" accept="audio/*" className="hidden" onChange={onFile} />
              </label>
            </div>
            {recording && <p className="text-xs text-red-500 animate-pulse">Recording… speak clearly.</p>}
            <p className="text-xs text-gray-400">
              {status?.sample_count || 0} sample{status?.sample_count === 1 ? "" : "s"} captured. Read the calibration
              script below and record 2-3 minutes total for the best clone.
            </p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm font-medium mb-2">📜 Calibration script (pronunciations + word formulation)</p>
            <div className="flex gap-2 mb-3">
              <input
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="Focus (optional): e.g. technical words, my name, accents"
                className="flex-1 border rounded px-3 py-2 text-sm"
              />
              <button onClick={generateScript} disabled={busy} className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
                Generate
              </button>
            </div>
            {script && (
              <div className="relative bg-gray-50 border rounded p-3 text-sm whitespace-pre-wrap">
                <button onClick={copyScript} className="absolute top-2 right-2 text-xs px-2 py-1 rounded border bg-white text-gray-500 hover:bg-gray-100">
                  ⧉ Copy
                </button>
                {script}
              </div>
            )}
          </div>
        </div>

        {/* Right: clone + sample list */}
        <div className="space-y-4">
          <button
            onClick={clone}
            disabled={busy || (status?.sample_count || 0) === 0}
            className="w-full py-3 rounded-lg font-medium text-white bg-purple-700 hover:bg-purple-800 transition disabled:opacity-50"
          >
            🧬 Clone my signature voice
          </button>
          <p className="text-xs text-gray-500">
            {status?.signature_active
              ? "KUDOS already has your signature voice and will use it for every spoken reply."
              : "Cloning captures your tone, pronunciation and word formulation so KUDOS speaks like you on every platform."}
          </p>

          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm font-medium mb-2">Your captured samples ({samples.length})</p>
            {samples.length === 0 ? (
              <p className="text-xs text-gray-400">No samples yet — record or upload your voice above.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {samples.map((s) => (
                  <div key={s.id} className="text-xs border-b pb-2">
                    <p className="text-gray-500">#{s.id} · {Math.max(1, s.duration_seconds)}s · {s.mime}</p>
                    <p className="text-gray-700">{s.transcribed || "(not transcribed)"}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
