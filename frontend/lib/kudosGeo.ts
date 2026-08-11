/**
 * KUDOS Maps + Network client — internal world map, crowdsourced device
 * location and terrestrial <-> satellite link switching.
 *
 * All calls go through the Next.js proxy (apiFetch) so session-cookie auth
 * and the CSRF header are handled automatically.
 */
import { apiFetch } from "@/lib/api";

export interface WorldPlace {
  id: number;
  key: string;
  name: string;
  country: string;
  region: string;
  continent: string;
  place_type: string;
  lat: number | null;
  lon: number | null;
  description: string;
  aliases: string;
  importance: number;
}

export interface MapsStatus {
  world_map: {
    mode: string;
    total: number;
    with_coordinates: number;
    without_coordinates: number;
    by_type: Record<string, number>;
  };
  network_anchors: {
    access_points: number;
    cell_towers: number;
    total_scans: number;
    located_scans: number;
    method: string;
  };
}

export interface LocationFix {
  mode: string;
  lat: number | null;
  lon: number | null;
  accuracy_m: number | null;
  source: string;
  matches: number;
  spread_km: number;
}

export interface WhereResult {
  known: boolean;
  location: LocationFix | null;
  reason?: string;
  area?: { found: boolean; continent?: string; nearest?: { name: string; place_type: string; country: string; lat: number; lon: number } };
}

export interface NetworkChoice {
  mode: string;
  link: string;
  tier: string;
  tier_label: string;
  constrained: boolean;
  transports: string[];
  signal_dbm: number;
  reported_at: string | null;
  strategy?: Record<string, string>;
}

export interface NetworkDevice {
  device_id: number;
  device_name: string;
  platform: string;
  status: string;
  mode: string;
  latest: null | {
    primary_transport: string;
    transports: string;
    signal_dbm: number;
    metered: boolean;
    satellite: boolean;
    satellite_backhaul: boolean;
    bandwidth_kbps: number;
    rtt_ms: number;
    provider: string;
    reported_at: string | null;
  };
  choice: NetworkChoice;
}

export interface LinksSummary {
  mesh: {
    device_count: number;
    by_transport: Record<string, { count: number; last_reported: string | null }>;
    satellite_reports: number;
  };
  tiers: Record<string, string>;
}

export async function mapsStatus(): Promise<MapsStatus> {
  return apiFetch<MapsStatus>("/api/v1/maps/status");
}

export async function mapsSearch(q: string, limit = 15): Promise<{ query: string; results: WorldPlace[] }> {
  return apiFetch(`/api/v1/maps/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export async function mapsPlace(id: number): Promise<{ place: WorldPlace; nearby_world: Array<WorldPlace & { distance_km: number }> }> {
  return apiFetch(`/api/v1/maps/place/${id}`);
}

export async function mapsNearby(lat: number, lon: number, radiusKm = 250): Promise<{
  places: Array<WorldPlace & { distance_km: number }>;
  radio_towers: Array<{ place_id: number; name: string; country: string; distance_km: number; stations: number }>;
}> {
  return apiFetch(`/api/v1/maps/nearby?lat=${lat}&lon=${lon}&radius_km=${radiusKm}`);
}

export async function mapsBetween(a: string, b: string): Promise<{
  found: boolean;
  from?: WorldPlace;
  to?: WorldPlace;
  distance_km?: number;
  bearing_deg?: number;
  direction?: string;
  route_hint?: string;
  missing?: string;
}> {
  return apiFetch(`/api/v1/maps/between?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
}

export async function mapsWhere(): Promise<WhereResult> {
  return apiFetch<WhereResult>("/api/v1/maps/where");
}

export async function mapsReportScan(body: {
  gps?: { lat: number; lon: number; accuracy: number } | null;
  wifi?: Array<{ bssid: string; ssid?: string; rssi?: number }>;
  cells?: Array<{ mcc?: number; mnc?: number; lac?: number; cid?: number }>;
}, xDeviceToken = ""): Promise<{ location: LocationFix; device_id: number; anchors_learned: { wifi: boolean; cells: boolean } }> {
  const headers: Record<string, string> = {};
  if (xDeviceToken) headers["X-Device-Token"] = xDeviceToken;
  return apiFetch("/api/v1/maps/report-scan", { method: "POST", body: JSON.stringify(body), headers });
}

export async function mapsSeed(force = false): Promise<{ seeded: Record<string, number>; status: unknown }> {
  return apiFetch(`/api/v1/maps/seed?force=${force}`, { method: "POST" });
}

export async function networkStatus(): Promise<{ devices: NetworkDevice[] }> {
  return apiFetch<{ devices: NetworkDevice[] }>("/api/v1/network/status");
}

export async function networkCloseup(deviceToken: string): Promise<{ devices: NetworkDevice[] }> {
  return apiFetch<{ devices: NetworkDevice[] }>("/api/v1/network/status", {
    headers: { "X-Device-Token": deviceToken },
  });
}

export async function networkLinks(): Promise<LinksSummary> {
  return apiFetch<LinksSummary>("/api/v1/network/links");
}

export async function networkReport(body: Record<string, unknown>, xDeviceToken = ""): Promise<NetworkChoice & { recorded?: boolean }> {
  const headers: Record<string, string> = {};
  if (xDeviceToken) headers["X-Device-Token"] = xDeviceToken;
  return apiFetch("/api/v1/network/report", { method: "POST", body: JSON.stringify(body), headers });
}

export async function networkMode(mode: string, deviceId?: number, xDeviceToken = ""): Promise<NetworkChoice> {
  const qs = new URLSearchParams({ mode });
  if (deviceId) qs.set("device_id", String(deviceId));
  const headers: Record<string, string> = {};
  if (xDeviceToken) headers["X-Device-Token"] = xDeviceToken;
  return apiFetch(`/api/v1/network/mode?${qs.toString()}`, { method: "POST", headers });
}

export async function networkProbe(host = "1.1.1.1"): Promise<{
  measured: boolean;
  host: string;
  rtt_ms: number | null;
  tier_hint?: string;
  detail?: string;
}> {
  return apiFetch(`/api/v1/network/probe?host=${encodeURIComponent(host)}`, { method: "POST" });
}

export function osmLink(lat: number, lon: number, zoom = 12): string {
  return `https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&mlon=${lon.toFixed(5)}#map=${zoom}/${lat.toFixed(5)}/${lon.toFixed(5)}`;
}