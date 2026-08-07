// Shared WebRTC helpers for Studio video calls & broadcasts.
// Signaling uses the database-backed queue endpoints on the backend.

export function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function wsBase(): string {
  const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${typeof window !== "undefined" ? window.location.host : "localhost"}`;
}

export const rtcConfig: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

export interface PeerOpts {
  kind: "call" | "broadcast";
  roomId: number;
  remoteId: number;
  localStream?: MediaStream | null;
  remoteVideo?: HTMLVideoElement | HTMLAudioElement | null;
  onSignal: (signalType: string, payload: string) => void;
  onRemoteStream?: (stream: MediaStream) => void;
}

// Create a peer connection with tracks attached and ICE auto-signaling.
export function makePeerConnection(opts: PeerOpts): RTCPeerConnection {
  const pc = new RTCPeerConnection(rtcConfig);
  if (opts.localStream) {
    opts.localStream.getTracks().forEach((t) => pc.addTrack(t, opts.localStream as MediaStream));
  }
  pc.ontrack = (ev) => {
    const stream = ev.streams[0] ?? new MediaStream([ev.track]);
    if (opts.remoteVideo && opts.remoteVideo.srcObject !== stream) {
      opts.remoteVideo.srcObject = stream;
    }
    opts.onRemoteStream?.(stream);
  };
  pc.onicecandidate = (ev) => {
    if (ev.candidate) opts.onSignal("ice", JSON.stringify(ev.candidate));
  };
  return pc;
}

export async function handleSignal(
  pc: RTCPeerConnection,
  signalType: string,
  payload: string,
): Promise<void> {
  if (signalType === "offer") {
    await pc.setRemoteDescription({ type: "offer", sdp: JSON.parse(payload).sdp });
  } else if (signalType === "answer") {
    await pc.setRemoteDescription({ type: "answer", sdp: JSON.parse(payload).sdp });
  } else if (signalType === "ice") {
    try {
      await pc.addIceCandidate(JSON.parse(payload));
    } catch {
      // candidate arrived before remote description; ignore
    }
  }
}

export async function createOffer(pc: RTCPeerConnection, onSignal: (t: string, p: string) => void) {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  onSignal("offer", JSON.stringify({ sdp: offer.sdp }));
}

export async function createAnswer(pc: RTCPeerConnection, onSignal: (t: string, p: string) => void) {
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  onSignal("answer", JSON.stringify({ sdp: answer.sdp }));
}

export function stopTracks(stream?: MediaStream | null) {
  if (!stream) return;
  stream.getTracks().forEach((t) => t.stop());
}
