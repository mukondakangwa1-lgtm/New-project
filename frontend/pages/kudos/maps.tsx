import { useEffect, useState } from "react";
import Link from "next/link";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";
import { apiFetch } from "@/lib/api";
import {
  MapsStatus,
  NetworkChoice,
  WhereResult,
  WorldPlace,
  mapsBetween,
  mapsNearby,
  mapsPlace,
  mapsReportScan,
  mapsSearch,
  mapsSeed,
  mapsStatus,
  mapsWhere,
  osmLink,
} from "@/lib/kudosGeo";

const DEVICE_TOKEN_KEY = "kudos_web_device_token";

export default function KudosMaps() {
  const [status, setStatus] = useState<MapsStatus | null>(null);
  const [where, setWhere] = useState<WhereResult | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WorldPlace[]>([]);
  const [selected, setSelected] = useState<WorldPlace | null>(null);
  const [selectedNearby, setSelectedNearby] = useState<Array<WorldPlace & { distance_km: number }>>([]);
  const [nearby, setNearby] = useState<{ places: Array<WorldPlace & { distance_km: number }>; radio_towers: any[] } | null>(null);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [route, setRoute] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [gpsBusy, setGpsBusy] = useState(false);
  const [msg, setMsg] = useState({ text: "", type: "" });

  useEffect(() => {
    mapsStatus().then(setStatus).catch(() => {});
    mapsWhere().then(setWhere).catch(() => {});
  }, []);

  const notify = (text: string, type = "info") => setMsg({ text, type });

  const doSearch = async () => {
    if (!query.trim()) return;
    setBusy("search");
    try {
      const res = await mapsSearch(query);
      setResults(res.results);
      notify(res.results.length ? `${res.results.length} matches on the internal map.` : "No match — try another name.", "info");
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    } finally {
      setBusy("");
    }
  };

  const openPlace = async (p: WorldPlace) => {
    setSelected(p);
    setSelectedNearby([]);
    try {
      const detail = await mapsPlace(p.id);
      setSelectedNearby(detail.nearby_world);
    } catch {
      setSelectedNearby([]);
    }
  };

  const locateAround = async (lat: number, lon: number) => {
    setBusy("nearby");
    try {
      const res = await mapsNearby(lat, lon);
      setNearby(res);
      notify(`Found ${res.places.length} places and ${res.radio_towers.length} radio tower areas within range.`, "success");
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    } finally {
      setBusy("");
    }
  };

  const doRoute = async () => {
    if (!a.trim() || !b.trim()) return;
    setBusy("route");
    try {
      const res = await mapsBetween(a, b);
      setRoute(res);
      if (!res.found) notify(`Place "${res.missing ?? "?"}" is not on the internal map.`, "error");
    } catch (err: any) {
      notify(`❌ ${err.message}`, "error");
    } finally {
      setBusy("");
    }
  };

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

  const shareLocation = () => {
    if (!navigator.geolocation) {
      notify("Geolocation is not available in this browser.", "error");
      return;
    }
    setGpsBusy(true);
    notify("Requesting GPS fix…", "info");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const token = await ensureBrowserDevice();
          const fix = await mapsReportScan(
            { gps: { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy ?? 100 } },
            token
          );
          notify(`Fix measured: ${fix.location.mode.replace("-", " ")} (±${Math.round(fix.location.accuracy_m ?? 0)} m) — never guessed.`, "success");
          const w = await mapsWhere();
          setWhere(w);
          if (fix.location.lat != null && fix.location.lon != null) locateAround(fix.location.lat, fix.location.lon);
        } catch (err: any) {
          notify(`❌ ${err.message}`, "error");
        } finally {
          setGpsBusy(false);
        }
      },
      () => {
        setGpsBusy(false);
        notify("Location permission was denied — KUDOS will not guess where you are.", "error");
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  };

  const seed = async () => {
    setBusy("seed");
    try {
      const res = await mapsSeed(true);
      const s = res.seeded as Record<string, number>;
      notify(`Seeded ${s.total ?? Object.values(s).reduce((t: number, v) => t + (v || 0), 0)} places into the internal map.`, "success");
      mapsStatus().then(setStatus).catch(() => {});
    } catch (err: any) {
      notify(`❌ ${err.message} (admin only)`, "error");
    } finally {
      setBusy("");
    }
  };

  return (
    <RequireRole roles={["user", "student", "admin"]} redirectTo="/kudos">
      <Layout>
        <div className="min-h-screen bg-gray-50">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-gray-800">🗺️ KUDOS Maps</h1>
            <Link href="/kudos" className="text-sm text-purple-600 hover:underline">← back to KUDOS</Link>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            KUDOS&apos;s own offline map of the world — radio towers, crowdsourced device networks and seeded places.
            Every fix shows its measured source; nothing is ever guessed.
          </p>

          {msg.text && (
            <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${msg.type === "error" ? "bg-red-50 text-red-700" : msg.type === "success" ? "bg-green-50 text-green-700" : "bg-blue-50 text-blue-700"}`}>
              {msg.text}
            </div>
          )}

          {/* Status / offline badge */}
          {status && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {[
                { label: "World places", value: `${status.world_map.total}`, hint: `${status.world_map.with_coordinates} with coordinates` },
                { label: "Radio tower areas", value: `${(status as any).radio?.total_places ?? "—"}`, hint: "live globe", },
                { label: "Wi-Fi anchors", value: `${status.network_anchors.access_points}`, hint: status.network_anchors.method },
                { label: "Located scans", value: `${status.network_anchors.located_scans}`, hint: "never guessed" },
              ].map((c) => (
                <div key={c.label} className="bg-white border rounded-xl p-4 shadow-sm">
                  <div className="text-xs text-gray-400 uppercase">{c.label}</div>
                  <div className="text-2xl font-bold text-gray-800">{c.value}</div>
                  <div className="text-xs text-gray-400">{c.hint} {c.label === "World places" && "· offline-ready"}</div>
                </div>
              ))}
              <button
                onClick={seed}
                disabled={busy === "seed"}
                className="bg-zinc-100 border border-zinc-200 rounded-xl p-4 text-left hover:bg-zinc-50 col-span-2 md:col-span-4 mt-1 text-sm text-zinc-600"
              >
                {busy === "seed" ? "Seeding…" : "↻ Seed / refresh the internal world map (admin)"}
              </button>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4 mb-6">
            {/* Search */}
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h2 className="font-semibold mb-2">Search the world</h2>
              <div className="flex gap-2">
                <input
                  className="flex-1 border rounded-lg px-3 py-2 text-sm"
                  placeholder="e.g. Nairobi, Paris, London, Mount Kilimanjaro"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doSearch()}
                />
                <button onClick={doSearch} disabled={busy === "search"} className="bg-purple-600 text-white text-sm px-4 rounded-lg hover:bg-purple-700 disabled:opacity-50">
                  Search
                </button>
              </div>
              {results.length > 0 && (
                <ul className="mt-3 space-y-1 max-h-64 overflow-y-auto">
                  {results.map((p) => (
                    <li key={p.key}>
                      <button
                        onClick={() => openPlace(p)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-purple-50 ${selected?.id === p.id ? "bg-purple-50 border border-purple-200" : ""}`}
                      >
                        <span className="font-medium">{p.name}</span>
                        <span className="text-gray-400 text-xs"> · {p.place_type} · {p.country || p.continent}</span>
                        <span className="block text-xs text-gray-400">
                          {p.lat != null ? `📍 ${p.lat.toFixed(4)}, ${p.lon?.toFixed(4)}` : "• coordinates not known"}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Share my location */}
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h2 className="font-semibold mb-2">📍 Where am I?</h2>
              <p className="text-xs text-gray-500 mb-3">
                Share your GPS once so KUDOS can anchor nearby networks for you and others — offline precision without guessing.
              </p>
              <button
                onClick={shareLocation}
                disabled={gpsBusy}
                className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {gpsBusy ? "Measuring…" : "Share my location"}
              </button>
              {where?.known && where.location && (
                <div className="mt-3 text-sm">
                  <div className="font-medium">Known fix — {where.location.mode}</div>
                  <div className="text-gray-600">📍 {where.location.lat?.toFixed(5)}, {where.location.lon?.toFixed(5)}</div>
                  <div className="text-gray-500 text-xs">
                    ±{Math.round(where.location.accuracy_m ?? 0)} m · source: {where.location.source}
                  </div>
                  {where.area?.nearest && (
                    <div className="mt-1 text-xs text-gray-500">
                      Area: <span className="text-gray-700">{where.area.nearest.name}</span>
                      {where.area.continent ? ` · ${where.area.continent}` : ""}
                    </div>
                  )}
                  {where.location.lat != null && where.location.lon != null && (
                    <a className="text-purple-600 text-xs underline" target="_blank" rel="noreferrer" href={osmLink(where.location.lat, where.location.lon)}>
                      Open in OpenStreetMap →
                    </a>
                  )}
                </div>
              )}
              {where && !where.known && <p className="mt-3 text-xs text-gray-400">{where.reason}</p>}
            </div>
          </div>

          {/* Selected place detail */}
          {selected && (
            <div className="bg-white border rounded-xl p-4 shadow-sm mb-6">
              <h2 className="font-semibold">{selected.name} <span className="text-xs text-gray-400 font-normal capitalize">({selected.place_type})</span></h2>
              <p className="text-sm text-gray-600 mt-1">{selected.description}</p>
              <p className="text-sm mt-1">
                {selected.lat != null ? (
                  <>
                    <a href={osmLink(selected.lat, selected.lon!)} target="_blank" rel="noreferrer" className="text-purple-600 underline">
                      📍 {selected.lat.toFixed(4)}, {selected.lon?.toFixed(4)}
                    </a>
                    <button onClick={() => locateAround(selected.lat!, selected.lon!)} disabled={busy === "nearby"} className="ml-3 text-xs text-blue-600 underline">
                      What&apos;s nearby?
                    </button>
                  </>
                ) : (
                  <span className="text-xs text-gray-400">Coordinates not yet known — KUDOS will not invent them.</span>
                )}
              </p>
              {busy === "nearby" && <div className="text-xs text-gray-400 mt-2">Finding nearby places & radio towers…</div>}
              {selectedNearby.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs uppercase text-gray-400 mb-1">Nearby (within 60 km)</div>
                  <div className="flex flex-wrap gap-2">
                    {selectedNearby.map((n) => (
                      <button key={n.key} onClick={() => openPlace(n)} className="text-xs border rounded-full px-3 py-1 hover:bg-purple-50">
                        {n.name} <span className="text-gray-400">· {n.distance_km} km</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Nearby + route */}
          {nearby && (
            <div className="grid md:grid-cols-2 gap-4 mb-6">
              <div className="bg-white border rounded-xl p-4 shadow-sm">
                <h2 className="font-semibold mb-2">Nearby places</h2>
                {nearby.places.slice(0, 12).map((p) => (
                  <div key={p.key} className="flex justify-between text-sm border-b py-1 last:border-0">
                    <button onClick={() => openPlace(p)} className="hover:text-purple-600 text-left">{p.name}</button>
                    <span className="text-gray-400 text-xs">{p.distance_km} km</span>
                  </div>
                ))}
                {nearby.radio_towers.length > 0 && (
                  <>
                    <div className="text-xs uppercase text-gray-400 mt-3 mb-1">🎙️ Radio tower areas</div>
                    {nearby.radio_towers.slice(0, 5).map((r) => (
                      <div key={r.place_id} className="text-sm text-gray-600 py-0.5">
                        {r.name} <span className="text-gray-400 text-xs">· {r.distance_km} km · {r.stations} towers</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
              <div className="bg-white border rounded-xl p-4 shadow-sm">
                <h2 className="font-semibold mb-2">🧭 Route between places</h2>
                <div className="flex gap-2 mb-2">
                  <input className="flex-1 border rounded-lg px-3 py-2 text-sm" placeholder="From (e.g. Paris)" value={a} onChange={(e) => setA(e.target.value)} />
                  <input className="flex-1 border rounded-lg px-3 py-2 text-sm" placeholder="To (e.g. London)" value={b} onChange={(e) => setB(e.target.value)} />
                  <button onClick={doRoute} disabled={busy === "route"} className="bg-yellow-600 text-white text-sm px-4 rounded-lg hover:bg-yellow-700 disabled:opacity-50">
                    Go
                  </button>
                </div>
                {route?.found && route.route_hint && (
                  <div className="text-sm bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <div className="font-medium mb-1">{route.direction} · {route.distance_km} km</div>
                    <div className="text-gray-600">{route.route_hint}</div>
                    <div className="text-xs text-gray-400 mt-1">bearing {route.bearing_deg}° (initial)</div>
                  </div>
                )}
                {route && !route.found && <div className="text-sm text-red-600">{route.missing}</div>}
              </div>
            </div>
          )}
        </div>
      </div>
      </Layout>
    </RequireRole>
  );
}