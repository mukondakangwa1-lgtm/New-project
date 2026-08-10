import { useEffect, useRef, useState } from "react";
import { getAuthHeader } from "@/lib/api";

interface Continent {
  name: string;
  places: number;
  stations: number;
}
interface Place {
  place_id: string;
  name: string;
  country: string;
  continent: string;
  lat: number;
  lon: number;
  stations: number;
}
interface Station {
  id: string;
  title: string;
  place: string;
  country: string;
  genre: string;
  stream_url: string;
  frequency?: string;
  current_track?: string;
}

type Tab = "globe" | "search";

export default function RadioPanel() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("globe");
  const [continents, setContinents] = useState<Continent[]>([]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [currentPlace, setCurrentPlace] = useState<Place | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const auth = () => ({ headers: getAuthHeader() } as RequestInit);

  useEffect(() => {
    if (open && tab === "globe") {
      fetch("/api/v1/kudos/radio/overview", auth())
        .then((r) => r.json())
        .then((d) => {
          if (Array.isArray(d.continents)) setContinents(d.continents);
        })
        .catch(() => {});
    }
  }, [open, tab]);

  const selectPlace = async (place: Place) => {
    setCurrentPlace(place);
    setLoading(true);
    setStations([]);
    try {
      const res = await fetch(`/api/v1/kudos/radio/place/${place.place_id}`, auth());
      const d = await res.json();
      setStations(Array.isArray(d.stations) ? d.stations : []);
    } catch {
      setStations([]);
    }
    setLoading(false);
  };

  const doSearch = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/v1/kudos/radio/search?q=${encodeURIComponent(q.trim())}`,
        auth()
      );
      const d = await res.json();
      setPlaces(Array.isArray(d.places) ? d.places : []);
      setStations(Array.isArray(d.stations) ? d.stations : []);
      setCurrentPlace(null);
    } catch {
      setPlaces([]);
      setStations([]);
    }
    setLoading(false);
  };

  const togglePlay = (station: Station) => {
    if (playing === station.id) {
      audioRef.current?.pause();
      setPlaying(null);
      return;
    }
    if (audioRef.current) audioRef.current.pause();
    setPlaying(station.id);
    const audio = audioRef.current ?? new Audio();
    audio.src = station.stream_url;
    audio.crossOrigin = "anonymous";
    audio.play().catch(() => setPlaying(null));
    audioRef.current = audio;
  };

  const backToGlobe = () => {
    setCurrentPlace(null);
    setStations([]);
    if (tab === "search") setTab("globe");
  };

  return (
    <div className="border-t border-gray-100 bg-gradient-to-br from-emerald-50 to-teal-50">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-emerald-800 hover:bg-emerald-100/60 transition"
      >
        <span>📻 Radio — tune into the world</span>
        <span className="text-emerald-600">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4">
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setTab("globe")}
              className={`text-xs px-3 py-1 rounded-full ${tab === "globe" ? "bg-emerald-600 text-white" : "bg-white border text-gray-600"}`}
            >
              🌍 The Globe
            </button>
            <button
              onClick={() => setTab("search")}
              className={`text-xs px-3 py-1 rounded-full ${tab === "search" ? "bg-emerald-600 text-white" : "bg-white border text-gray-600"}`}
            >
              🔍 Search the world
            </button>
            {currentPlace && (
              <button
                onClick={backToGlobe}
                className="text-xs px-3 py-1 rounded-full bg-white border text-gray-600"
              >
                ← back
              </button>
            )}
          </div>

          {tab === "search" && (
            <div className="flex gap-2 mb-3">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doSearch()}
                placeholder="Search places & stations… (e.g. Tokyo, jazz, BBC)"
                className="flex-1 rounded-lg border px-3 py-2 text-sm"
              />
              <button
                onClick={doSearch}
                disabled={loading}
                className="bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                Search
              </button>
            </div>
          )}

          {loading && <p className="text-xs text-emerald-700 animate-pulse">Tuning in…</p>}

          {!currentPlace && !loading && tab === "globe" && (
            <div className="space-y-3">
              <p className="text-xs text-emerald-800 font-medium">
                {continents.length
                  ? `KUDOS knows ${continents.reduce((a, c) => a + c.places, 0)} places & ${continents.reduce((a, c) => a + c.stations, 0)} live radio towers`
                  : "KUDOS hasn't scanned the globe yet — run a scan from the Guardian page, or search below."}
              </p>
              {continents.map((c) => (
                <button
                  key={c.name}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      const res = await fetch(
                        `/api/v1/kudos/radio/search?q=${encodeURIComponent(c.name)}&limit=60`,
                        auth()
                      );
                      const d = await res.json();
                      setPlaces(Array.isArray(d.places) ? d.places : []);
                      setCurrentPlace(null);
                      setStations([]);
                    } catch {
                      setPlaces([]);
                    }
                    setLoading(false);
                  }}
                  className="w-full flex justify-between items-center bg-white border border-emerald-100 rounded-lg px-3 py-2 text-left hover:bg-emerald-50 transition"
                >
                  <span className="text-sm font-medium text-gray-800">{c.name}</span>
                  <span className="text-xs text-emerald-700">{c.places} places · {c.stations} stations</span>
                </button>
              ))}
            </div>
          )}

          {!currentPlace && !loading && places.length > 0 && (
            <div className="mt-3 space-y-1.5 max-h-60 overflow-y-auto">
              {places.map((p) => (
                <button
                  key={p.place_id}
                  onClick={() => selectPlace(p)}
                  className="w-full flex justify-between items-center bg-white border border-gray-100 rounded-lg px-3 py-2 text-left hover:bg-gray-50 transition"
                >
                  <span className="text-sm text-gray-800 truncate">
                    📍 {p.name}
                    {p.country ? <span className="text-gray-400 text-xs"> — {p.country}</span> : null}
                  </span>
                  <span className="text-xs text-gray-500 whitespace-nowrap ml-2">
                    {p.lat.toFixed(1)}, {p.lon.toFixed(1)} · {p.stations} 📻
                  </span>
                </button>
              ))}
            </div>
          )}

          {currentPlace && (
            <div className="mt-2">
              <p className="text-sm font-semibold text-gray-800 mb-1">
                📍 {currentPlace.name}
                <span className="text-xs text-gray-400 font-normal">
                  {" "}— {currentPlace.country} ({currentPlace.lat.toFixed(2)}, {currentPlace.lon.toFixed(2)})
                </span>
              </p>
              {stations.length === 0 && !loading && (
                <p className="text-xs text-gray-500">No live radio towers found here.</p>
              )}
              <div className="space-y-1.5 max-h-72 overflow-y-auto">
                {stations.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center gap-3 bg-white border border-gray-100 rounded-lg px-3 py-2"
                  >
                    <button
                      onClick={() => togglePlay(s)}
                      className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs transition ${
                        playing === s.id
                          ? "bg-red-500 text-white"
                          : "bg-emerald-600 text-white hover:bg-emerald-700"
                      }`}
                      title={playing === s.id ? "Stop" : "Play"}
                    >
                      {playing === s.id ? "⏹" : "▶"}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-gray-800 truncate">{s.title}</p>
                      <p className="text-xs text-gray-500 truncate">
                        {[s.genre, s.frequency, s.current_track].filter(Boolean).join(" · ") || s.place}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
