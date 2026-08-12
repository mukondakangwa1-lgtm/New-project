import { useEffect, useState, type ReactNode } from "react";
import { getAuthHeader } from "@/lib/api";
import { CopyButton } from "@/components/MessageContent";

export type SiteKind = "site" | "cv" | "company_profile";

interface SiteMeta {
  site_id: string;
  name: string;
  kind: string;
  title: string;
  created_at: string;
  url: string;
}

interface SiteMakerProps {
  open: boolean;
  kind: SiteKind;
  onClose: () => void;
}

/** Smooth public URL for a site (viewable by registered and anonymous users). */
const siteHref = (site: SiteMeta) => `/s/${site.site_id}`;

const KIND_INFO: Record<SiteKind, { icon: string; title: string; blurb: string; cta: string }> = {
  site: {
    icon: "🌐",
    title: "Website Maker",
    blurb: "Describe any website in a line or two — KUDOS builds it and launches it live on the network.",
    cta: "⚡ Build website",
  },
  cv: {
    icon: "📄",
    title: "CV / Resume Maker",
    blurb: "Fill in your details and KUDOS lays out a clean, professional one-page CV.",
    cta: "⚡ Build my CV",
  },
  company_profile: {
    icon: "🏢",
    title: "Company Profile Maker",
    blurb: "Drop in your company details — get a polished public profile page in seconds.",
    cta: "⚡ Build profile",
  },
};

const inputCls =
  "w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-400";

function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`block ${wide ? "col-span-2" : ""}`}>
      <span className="block text-xs font-medium text-zinc-400 mb-1">{label}</span>
      {children}
    </label>
  );
}

export default function SiteMaker({ open, kind, onClose }: SiteMakerProps) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [profile, setProfile] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<SiteMeta | null>(null);
  const [sites, setSites] = useState<SiteMeta[]>([]);

  const setP = (key: string, value: string) => setProfile((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    if (!open) return;
    setCreated(null);
    setError("");
    setBusy(false);
    fetch("/api/v1/kudos/sites")
      .then((r) => r.json())
      .then((d) => setSites(Array.isArray(d.sites) ? d.sites : []))
      .catch(() => setSites([]));
  }, [open, kind]);

  if (!open) return null;

  const profileData = () => {
    if (kind === "cv") {
      return {
        name: profile.name || "",
        title: profile.title || "",
        email: profile.email || "",
        phone: profile.phone || "",
        location: profile.location || "",
        summary: profile.summary || "",
        skills: (profile.skills || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        experience: (profile.experience || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        education: (profile.education || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      };
    }
    if (kind === "company_profile") {
      return {
        company_name: profile.company_name || "",
        tagline: profile.tagline || "",
        industry: profile.industry || "",
        services: (profile.services || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        description: profile.description || "",
        contact_email: profile.contact_email || "",
      };
    }
    return null;
  };

  const create = async () => {
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      const res = await fetch("/api/v1/kudos/sites", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({
          name: name.trim(),
          kind,
          prompt: prompt.trim(),
          profile_data: kind === "site" ? null : profileData(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "KUDOS couldn't build the site.");
      setCreated(data);
      setSites((prev) => [data, ...prev.filter((s) => s.site_id !== data.site_id)]);
    } catch (e: any) {
      setError(e.message || "Build failed.");
    } finally {
      setBusy(false);
    }
  };

  const removeSite = async (site: SiteMeta) => {
    if (!window.confirm(`Delete "${site.name}"?`)) return;
    try {
      await fetch(`/api/v1/kudos/sites/${site.site_id}`, {
        method: "DELETE",
        headers: getAuthHeader(),
      });
      setSites((prev) => prev.filter((s) => s.site_id !== site.site_id));
    } catch {
      /* best-effort */
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-700 bg-gradient-to-r from-amber-500/15 to-transparent">
          <div>
            <h3 className="text-lg font-bold text-zinc-100">
              {KIND_INFO[kind].icon} {KIND_INFO[kind].title}
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">{KIND_INFO[kind].blurb}</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-100 flex items-center justify-center text-sm transition"
            title="Close"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Result */}
          {created && (
            <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-amber-300">🎉 Live! {created!.name || created!.title}</p>
                  <p className="text-xs text-zinc-400 mt-0.5">{created!.kind} · {new Date(created!.created_at).toLocaleString()}</p>
                </div>
                <CopyButton text={window.location.origin + siteHref(created!)} label="⧉ Copy link" />
              </div>
              <div className="flex gap-2 mt-3">
                <a
                  href={siteHref(created!)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 text-center bg-amber-500 text-zinc-950 text-sm font-semibold py-2 rounded-lg hover:bg-amber-400 transition"
                >
                  🚀 Open live site
                </a>
                <button onClick={() => setCreated(null)} className="px-4 py-2 rounded-lg border border-zinc-700 text-xs text-zinc-300 hover:bg-zinc-800 transition">
                  Build another
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              ⚠️ {error}
            </div>
          )}

          {/* Build form */}
          {!created && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Name / label">
                  <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={kind === "cv" ? "e.g. Ada Lovelace" : kind === "company_profile" ? "e.g. Acme Ltd" : "e.g. My Garden Store"} maxLength={120} />
                </Field>
                {kind === "site" && (
                  <Field label="Kind" wide={false}>
                    <div className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-400">🌐 website</div>
                  </Field>
                )}
              </div>

              {kind === "site" && (
                <Field label="What should the website be?">
                  <textarea
                    className={`${inputCls} resize-none`}
                    rows={4}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g. A bakery website with hero, menu, gallery and contact section — warm cream & brown tones…"
                    maxLength={2000}
                  />
                </Field>
              )}

              {kind === "cv" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Job title">
                    <input className={inputCls} value={profile.title || ""} onChange={(e) => setP("title", e.target.value)} placeholder="Software Engineer" />
                  </Field>
                  <Field label="Location">
                    <input className={inputCls} value={profile.location || ""} onChange={(e) => setP("location", e.target.value)} placeholder="Harare, Zimbabwe" />
                  </Field>
                  <Field label="Email">
                    <input className={inputCls} value={profile.email || ""} onChange={(e) => setP("email", e.target.value)} placeholder="you@email.com" />
                  </Field>
                  <Field label="Phone">
                    <input className={inputCls} value={profile.phone || ""} onChange={(e) => setP("phone", e.target.value)} placeholder="+263 …" />
                  </Field>
                  <Field label="Professional summary" wide>
                    <textarea className={`${inputCls} resize-none`} rows={2} value={profile.summary || ""} onChange={(e) => setP("summary", e.target.value)} placeholder="A short 2–3 sentence bio…" />
                  </Field>
                  <Field label="Skills (one per line)" wide>
                    <textarea className={`${inputCls} resize-none`} rows={3} value={profile.skills || ""} onChange={(e) => setP("skills", e.target.value)} placeholder={"Python\nFastAPI\nReact\nLeadership"} />
                  </Field>
                  <Field label="Experience (one role per line)" wide>
                    <textarea className={`${inputCls} resize-none`} rows={3} value={profile.experience || ""} onChange={(e) => setP("experience", e.target.value)} placeholder={"Lead Engineer, Acme — 2021–now\nJunior Dev, Beta — 2019–2021"} />
                  </Field>
                  <Field label="Education (one per line)" wide>
                    <textarea className={`${inputCls} resize-none`} rows={2} value={profile.education || ""} onChange={(e) => setP("education", e.target.value)} placeholder={"BSc Computer Science, UZ — 2019"} />
                  </Field>
                </div>
              )}

              {kind === "company_profile" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Company name">
                    <input className={inputCls} value={profile.company_name || ""} onChange={(e) => setP("company_name", e.target.value)} placeholder="Acme Ltd" />
                  </Field>
                  <Field label="Industry">
                    <input className={inputCls} value={profile.industry || ""} onChange={(e) => setP("industry", e.target.value)} placeholder="AgriTech / Retail / Education…" />
                  </Field>
                  <Field label="Tagline" wide>
                    <input className={inputCls} value={profile.tagline || ""} onChange={(e) => setP("tagline", e.target.value)} placeholder="One-line tagline…" />
                  </Field>
                  <Field label="Description / About" wide>
                    <textarea className={`${inputCls} resize-none`} rows={2} value={profile.description || ""} onChange={(e) => setP("description", e.target.value)} placeholder="What does the company do?" />
                  </Field>
                  <Field label="Services (one per line)" wide>
                    <textarea className={`${inputCls} resize-none`} rows={3} value={profile.services || ""} onChange={(e) => setP("services", e.target.value)} placeholder={"Grain trading\nWarehousing\nFarm advisory"} />
                  </Field>
                  <Field label="Contact email" wide>
                    <input className={inputCls} value={profile.contact_email || ""} onChange={(e) => setP("contact_email", e.target.value)} placeholder="hello@acme.com" />
                  </Field>
                </div>
              )}

              <button
                onClick={create}
                disabled={busy}
                className="w-full bg-amber-500 text-zinc-950 font-semibold py-3 rounded-xl hover:bg-amber-400 active:scale-[0.99] transition disabled:opacity-60"
              >
                {busy ? "KUDOS is designing…" : KIND_INFO[kind].cta}
              </button>
            </>
          )}

          {/* Launched sites */}
          {sites.length > 0 && (
            <div className="pt-2 border-t border-zinc-800">
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">🖥️ Launched on the network</p>
              <div className="space-y-1.5">
                {sites.map((s) => (
                  <div key={s.site_id} className="flex items-center gap-2 rounded-lg bg-zinc-800/60 border border-zinc-800 px-3 py-2">
                    <a href={siteHref(s)} target="_blank" rel="noreferrer" className="flex-1 min-w-0 text-sm text-zinc-200 hover:text-amber-300 truncate transition">
                      🖥️ {s.name || s.title}
                      <span className="text-xs text-zinc-500 ml-2">{s.kind}</span>
                    </a>
                    <CopyButton text={window.location.origin + siteHref(s)} label="⧉" />
                    <button
                      onClick={() => removeSite(s)}
                      className="text-xs text-zinc-500 hover:text-red-400 transition"
                      title="Delete site"
                    >
                      🗑
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}