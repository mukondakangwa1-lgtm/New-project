/**
 * Automatic KUDOS network mapping.
 *
 * Any device running KUDOS (guests included) registers itself as a device and
 * reports its real, browser-measured link — transport, RTT, bandwidth — so the
 * KUDOS mesh always knows what each device actually has, without anyone typing
 * it in. The admin's Networks page stays fully manual for override/probes.
 *
 * Backend: POST /kudos/devices (guest-safe) then POST /network/report with the
 * X-Device-Token header. Reports run on load, on network change, and whenever
 * the tab becomes visible again, throttled to avoid spamming.
 */

import { apiFetch } from "@/lib/api";

const DEVICE_TOKEN_KEY = "kudos_web_device_token";
const THROTTLE_MS = 60_000;

interface ConnectionLike {
  type?: string;
  effectiveType?: string;
  rtt?: number;
  downlink?: number;
  saveData?: boolean;
}

function getConnection(): ConnectionLike | null {
  if (typeof navigator === "undefined") return null;
  const anyNav = navigator as any;
  return anyNav.connection || anyNav.mozConnection || anyNav.webkitConnection || null;
}

function transportFor(conn: ConnectionLike | null): string {
  if (!conn) return "unknown";
  const type = (conn.type || "").toLowerCase();
  if (type === "wifi" || type === "ethernet") return type;
  if (type === "cellular" || type === "bluetooth" || type === "wimax") return "cellular";
  if (type === "none") return "unknown";
  const eff = (conn.effectiveType || "").toLowerCase();
  if (eff.startsWith("4g") || eff.startsWith("3g")) return "cellular";
  if (eff.startsWith("2g")) return "cellular";
  return "unknown";
}

function bandwidthKbps(conn: ConnectionLike | null): number | undefined {
  if (conn && typeof conn.downlink === "number" && conn.downlink > 0) {
    return Math.round(conn.downlink * 1024);
  }
  return undefined;
}

function rttMs(conn: ConnectionLike | null): number | undefined {
  if (conn && typeof conn.rtt === "number" && conn.rtt > 0) return conn.rtt;
  return undefined;
}

let lastReport = 0;

export async function reportLink(force = false): Promise<void> {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (!force && now - lastReport < THROTTLE_MS) return;

  try {
    const conn = getConnection();
    const primary = transportFor(conn);
    const payload: Record<string, unknown> = {
      primary_transport: primary,
      transports: [primary],
      metered: Boolean(conn?.saveData),
      constrained: false,
      satellite: false,
      satellite_backhaul: false,
    };
    const bw = bandwidthKbps(conn);
    if (bw !== undefined) payload.bandwidth_kbps = bw;
    const rtt = rttMs(conn);
    if (rtt !== undefined) payload.rtt_ms = rtt;

    let token = localStorage.getItem(DEVICE_TOKEN_KEY);
    if (!token) {
      try {
        const device = await apiFetch<any>("/api/v1/kudos/devices", {
          method: "POST",
          body: JSON.stringify({ name: "Web Browser", platform: "web", storage_bytes: 268435456 }),
          auth: false,
        });
        token = device?.api_token;
        if (token) localStorage.setItem(DEVICE_TOKEN_KEY, token);
      } catch {
        // Device registration failed (e.g. server unreachable) — skip silently.
        return;
      }
    }
    if (!token) return;

    await apiFetch("/api/v1/network/report", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "X-Device-Token": token },
      auth: false,
    });
    lastReport = Date.now();
  } catch {
    // Best-effort: a failed report must never break a page.
  }
}

export function startAutoNetworkReporter(): () => void {
  if (typeof window === "undefined") return () => {};

  const fire = () => reportLink();
  const force = () => reportLink(true);

  // Initial report once the page is ready.
  if (document.readyState === "complete") {
    fire();
  } else {
    window.addEventListener("load", fire, { once: true });
  }

  // Re-report when the device's network changes.
  const conn = getConnection() as any;
  conn?.addEventListener?.("change", force);

  // And when the tab comes back into view (device may have moved links).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") fire();
  });

  window.addEventListener("online", force);
  window.addEventListener("offline", force);

  return () => {
    window.removeEventListener("load", fire);
    conn?.removeEventListener?.("change", force);
    document.removeEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") fire();
    });
    window.removeEventListener("online", force);
    window.removeEventListener("offline", force);
  };
}
