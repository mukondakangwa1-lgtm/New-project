import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { apiFetch } from "@/lib/api";
import {
  networkLinks,
  networkMode,
  networkReport,
  networkStatus,
  LinksSummary,
  NetworkChoice,
  NetworkDevice,
} from "@/lib/kudosGeo";

const DEVICE_TOKEN_KEY = "kudos_web_device_token";

const TRANSPORTS = ["wifi", "cellular", "ethernet", "satellite"] as const;
const TIER_COLORS: Record<string, string> = {
  full: "text-green-700 bg-green-50 border-green-200",
  constrained: "text-amber-700 bg-amber-50 border-amber-200",
  emergency: "text-red-700 bg-red-50 border-red-200",
};

export default function KudosNetworks() {
  const [summary, setSummary] = useState<LinksSummary | null>(null);
  const [devices, setDevices] = useState<NetworkDevice[]>([]);
  const [transport, setTransport] = useState<string>("wifi");
  const [satellite, setSatellite] = useState(false);
  const [backhaul, setBackhaul] = useState(false);
  const [rtt, setRtt] = useState("");
  const [signal, setSignal] = useState("");
  const [provider, setProvider] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const [probeBusy, setProbeBusy] = useState(false);
  const [probeHost, setProbeHost] = useState("1.1.1.1");
  const [probe, setProbe] = useState<any>(null);
  const [lastChoice, setLastChoice] = useState<(NetworkChoice & { recorded?: boolean }) | null>(null);
  const [msg, setMsg] = useState({ text: "", type: "" });

  useEffect(() => {
    networkStatus().then((s) => setDevices(s.devices)).catch(() => {});
    networkLinks().then(setSummary).catch(() => {});
  }, []);

  const notify = (text: string, type = "info") => setMsg({ text, type });

  const ensureBrowserDevice = async (): Promise<string> => {
    const cached = localStorage.getItem(DEVICE_TOKEN_KEY);
    if (cached) return cached;
    const device = await apiFetch<any>("/api/v1/kudos/devices", {
      method: "POST",
      body: JSON.stringify({ name: "Web Browser", platform: "web", storage_bytes: 268435456 }),
    });
    localStorage.setItem(DEVICE_TOKEN_KEY, device.api_token);
    return device.api_token;
  };

  const reportLink = async () => {
    setReportBusy(true);
    try {
      const token = await ensureBrowserDevice();
      const res = await networkReport(
        {
          primary_transport: transport,
          transports: [transport],
          signal_dbm: signal ? Number(signal) : undefined,
          satellite: transport === "satellite" || satellite,
          satellite_backhaul: transport === "satellite" || backhaul,
          constrained: transport === "satellite" || backhaul,
          rtt_ms: rtt ? Number(rtt) : undefined,
          provider,
        },
        token
      );
      setLastChoice(res);
      notify(`Link reported — KUDOS chose ${res.link} (${res.tier_label}).`, "success");
      const s = await networkStatus();
      setDevices(s.devices);
      const l = await networkLinks();
      setSummary(l);
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    } finally {
      setReportBusy(false);
    }
  };

  const setMode = async (deviceId: number, mode: string) => {
    try {
      await networkMode(mode, deviceId, localStorage.getItem(DEVICE_TOKEN_KEY) ?? "");
      notify(`Device ${deviceId} → mode ${mode}.`, "success");
      const s = await networkStatus();
      setDevices(s.devices);
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    }
  };

  const runProbe = async () => {
    setProbeBusy(true);
    try {
      const res = await fetch(`/api/v1/network/probe?host=${encodeURIComponent(probeHost)}`, { method: "POST" }).then((r) => r.json());
      setProbe(res);
      notify(res.measured ? `Measured ${res.rtt_ms} ms via ${res.host} — tier: ${res.tier_hint}` : "Probe failed — nothing measured.", res.measured ? "success" : "error");
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    } finally {
      setProbeBusy(false);
    }
  };

  return (
    <Layout>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-gray-800">📡 KUDOS Networks</h1>
            <a href="/kudos" className="text-sm text-purple-600 hover:underline">← back to KUDOS</a>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Terrestrial ↔ satellite link switching. KUDOS measures what your device actually has and applies Auto /
            Terrestrial / Satellite preference — it never claims a link it hasn&apos;t measured.
          </p>

          {msg.text && (
            <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${msg.type === "error" ? "bg-red-50 text-red-700" : msg.type === "success" ? "bg-green-50 text-green-700" : "bg-blue-50 text-blue-700"}`}>
              {msg.text}
            </div>
          )}

          {/* Mesh summary */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="bg-white border rounded-xl p-4 shadow-sm">
                <div className="text-xs text-gray-400 uppercase">Devices</div>
                <div className="text-2xl font-bold text-gray-800">{summary.mesh.device_count}</div>
                <div className="text-xs text-gray-400">in the mesh</div>
              </div>
              <div className="bg-white border rounded-xl p-4 shadow-sm">
                <div className="text-xs text-gray-400 uppercase">Satellite</div>
                <div className="text-2xl font-bold text-gray-800">{summary.mesh.satellite_reports}</div>
                <div className="text-xs text-gray-400">satellite reports</div>
              </div>
              <div className="bg-white border rounded-xl p-4 shadow-sm col-span-2">
                <div className="text-xs text-gray-400 uppercase mb-1">Transport mix (latest per device)</div>
                <div className="flex flex-wrap gap-2 text-sm">
                  {Object.entries(summary.mesh.by_transport).map(([t, v]) => (
                    <span key={t} className="border rounded-full px-3 py-1">
                      {t} <b>{v.count}</b>
                    </span>
                  ))}
                  {Object.keys(summary.mesh.by_transport).length === 0 && <span className="text-gray-400 text-sm">No reports yet</span>}
                </div>
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4 mb-6">
            {/* Report your link */}
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h2 className="font-semibold mb-2">🛰️ Report this device&apos;s link</h2>
              <p className="text-xs text-gray-500 mb-3">KUDOS records only what is actually measured — RSSI, latency, satellite/backhaul flags.</p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-500">Primary transport</label>
                  <select value={transport} onChange={(e) => setTransport(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
                    {TRANSPORTS.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={satellite} onChange={(e) => setSatellite(e.target.checked)} /> TRANSPORT_SATELLITE</label>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={backhaul} onChange={(e) => setBackhaul(e.target.checked)} /> Satellite backhaul</label>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <input className="border rounded-lg px-3 py-2 text-sm" placeholder="RSSI dBm" value={signal} onChange={(e) => setSignal(e.target.value)} />
                  <input className="border rounded-lg px-3 py-2 text-sm" placeholder="RTT ms" value={rtt} onChange={(e) => setRtt(e.target.value)} />
                  <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} />
                </div>
                <button onClick={reportLink} disabled={reportBusy} className="w-full bg-purple-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50">
                  {reportBusy ? "Reporting…" : "Report link → get strategy"}
                </button>
                {lastChoice && (
                  <div className="text-sm bg-blue-50 border border-blue-100 rounded-lg p-3">
                    <div className="font-medium">Chosen link: <code>{lastChoice.link}</code> · tier: <span className="capitalize">{lastChoice.tier}</span></div>
                    <div className="text-xs text-gray-600 mt-1">mode {lastChoice.mode} · {lastChoice.transports.join(" / ")} · signal {lastChoice.signal_dbm} dBm</div>
                    {lastChoice.strategy && (
                      <ul className="mt-2 text-xs text-gray-600 grid grid-cols-2 gap-1">
                        {Object.entries(lastChoice.strategy).map(([k, v]) => (
                          <li key={k}><span className="font-medium">{k}</span>: {String(v)}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Probe */}
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h2 className="font-semibold mb-2">⏱️ Live link probe</h2>
              <p className="text-xs text-gray-500 mb-3">Measures actual RTT through the current link — the measured value, not a guess.</p>
              <div className="flex gap-2">
                <input className="flex-1 border rounded-lg px-3 py-2 text-sm" value={probeHost} onChange={(e) => setProbeHost(e.target.value)} />
                <button onClick={runProbe} disabled={probeBusy} className="bg-blue-600 text-white text-sm px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {probeBusy ? "Probing…" : "Probe"}
                </button>
              </div>
              {probe && (
                <div className="mt-3 text-sm">
                  {probe.measured ? (
                    <>
                      <div><span className="text-gray-500">rtt:</span> <b>{probe.rtt_ms} ms</b></div>
                      <div><span className="text-gray-500">tier hint:</span> {probe.tier_hint}</div>
                    </>
                  ) : (
                    <div className="text-red-600">{probe.detail}</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Mesh closeup */}
          {devices.length > 0 && (
            <div className="bg-white border rounded-xl p-4 shadow-sm mb-6">
              <h2 className="font-semibold mb-3">Devices</h2>
              <div className="space-y-2">
                {devices.map((d) => (
                  <div key={d.device_id} className="border rounded-lg p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <span className="font-medium">{d.device_name}</span>
                        <span className="text-xs text-gray-400 ml-1">· {d.platform}</span>
                        <span className={`text-xs ml-2 border rounded-full px-2 py-0.5 ${TIER_COLORS[d.choice.tier] ?? "text-gray-600 bg-gray-50 border-gray-200"}`}>
                          {d.choice.tier}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex rounded-lg border overflow-hidden text-xs">
                          {["auto", "terrestrial", "satellite"].map((m) => (
                            <button key={m} onClick={() => setMode(d.device_id, m)}
                              className={`px-3 py-1 ${d.mode === m ? "bg-purple-600 text-white" : "hover:bg-purple-50"}`}>
                              {m}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {d.latest ? (
                        <>
                          <b className="uppercase">{d.latest.primary_transport}</b>
                          {" · "}{d.latest.transports}
                          {" · "}{d.latest.signal_dbm} dBm
                          {" · rtt "}{d.latest.rtt_ms} ms
                          {d.latest.satellite ? " · 🛰️ sat" : ""}
                          {d.latest.satellite_backhaul ? " · backhaul" : ""}
                          {d.latest.provider ? ` · ${d.latest.provider}` : ""}
                        </>
                      ) : "no report yet"}
                      <span className="text-gray-400"> → link: <b>{d.choice.link}</b> · {d.choice.tier_label}</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-3 mb-1">Strategy applied when tier is constrained</p>
            </div>
          )}

          {devices.length === 0 && (
            <div className="bg-white border rounded-xl p-6 text-center text-sm text-gray-400 mb-6">
              No devices in the mesh yet. Report your link above — KUDOS registers this browser as a device.
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}