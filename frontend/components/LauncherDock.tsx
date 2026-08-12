import { useState } from "react";
import type { SiteKind } from "@/components/SiteMaker";

/* ── Mini live preview tiles ────────────────────────────────────────────── */

/** Browser-window mockup that "types" a page: hero, copy, columns. */
function WebPreview() {
  return (
    <div className="lift-bob relative w-14 h-10 shrink-0 rounded-md bg-zinc-950 border border-zinc-700/80 overflow-hidden shadow-lg shadow-black/40">
      <div className="h-2 bg-zinc-800 flex items-center gap-0.5 px-1 border-b border-zinc-700/60">
        <span className="w-1 h-1 rounded-full bg-red-400" />
        <span className="w-1 h-1 rounded-full bg-amber-400" />
        <span className="w-1 h-1 rounded-full bg-emerald-400" />
        <span className="ml-1 h-1 w-4 rounded-full bg-zinc-600" />
      </div>
      <div className="h-2.5 bg-gradient-to-r from-amber-600 to-amber-300" />
      <div className="preview-line mt-0.5 mx-1 h-0.5 w-2/3 rounded-full bg-zinc-400/80" />
      <div className="flex gap-0.5 mt-0.5 mx-1">
        <div className="preview-line-2 h-1.5 flex-1 rounded-sm bg-zinc-600" />
        <div className="preview-line-3 h-1.5 flex-1 rounded-sm bg-zinc-700" />
        <div className="preview-line h-1.5 flex-1 rounded-sm bg-zinc-600" />
      </div>
      <div className="shimmer-layer">
        <div className="shimmer-sweep" />
      </div>
    </div>
  );
}

/** One-page document with a running scan line. */
function CvPreview() {
  return (
    <div className="lift-bob relative w-14 h-10 shrink-0 rounded-md bg-zinc-950 border border-zinc-700/80 overflow-hidden shadow-lg shadow-black/40">
      <div className="h-2.5 bg-zinc-800 flex items-center gap-1 px-1 border-b border-zinc-700/60">
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
        <span className="h-0.5 w-6 rounded-full bg-zinc-400/80" />
      </div>
      <div className="preview-line mt-1 mx-1 h-0.5 w-3/4 rounded-full bg-zinc-500/90" />
      <div className="preview-line-2 mx-1 mt-0.5 h-0.5 w-full rounded-full bg-zinc-700" />
      <div className="preview-line-3 mx-1 mt-0.5 h-0.5 w-5/6 rounded-full bg-zinc-700" />
      <div className="preview-line mx-1 mt-0.5 h-0.5 w-2/3 rounded-full bg-zinc-700" />
      <div className="shimmer-layer">
        <div className="shimmer-sweep" />
      </div>
    </div>
  );
}

/** Company card: logo, tagline, service chips. */
function CompanyPreview() {
  return (
    <div className="lift-bob relative w-14 h-10 shrink-0 rounded-md bg-zinc-950 border border-zinc-700/80 overflow-hidden shadow-lg shadow-black/40">
      <div className="h-2 bg-gradient-to-r from-amber-700/70 to-amber-500/50 flex items-center justify-center">
        <span className="h-1 w-3 rounded-full bg-amber-300" />
      </div>
      <div className="flex items-center gap-1 mt-1 mx-1">
        <span className="preview-line w-2.5 h-2.5 rounded-full bg-amber-500/80" />
        <span className="h-0.5 w-7 rounded-full bg-zinc-400/90" />
      </div>
      <div className="preview-line-2 mx-1 mt-0.5 h-0.5 w-4/5 rounded-full bg-zinc-700" />
      <div className="flex gap-0.5 mt-1 mx-1">
        <span className="preview-line-3 px-0.5 h-1.5 rounded-sm bg-amber-500/30 text-[4px] leading-none text-amber-300/90 font-bold">SVC</span>
        <span className="preview-line px-0.5 h-1.5 rounded-sm bg-amber-500/20 text-[4px] leading-none text-amber-300/80 font-bold">SVC</span>
        <span className="preview-line-2 px-0.5 h-1.5 rounded-sm bg-amber-500/25 text-[4px] leading-none text-amber-300/90 font-bold">SVC</span>
      </div>
      <div className="shimmer-layer">
        <div className="shimmer-sweep" />
      </div>
    </div>
  );
}

const MAKERS: Array<{ kind: SiteKind; icon: string; label: string; hint: string; Preview: () => JSX.Element }> = [
  { kind: "site", icon: "🌐", label: "Website", hint: "A live site in seconds", Preview: WebPreview },
  { kind: "cv", icon: "📄", label: "CV / Resume", hint: "One-page, print-ready", Preview: CvPreview },
  { kind: "company_profile", icon: "🏢", label: "Company Profile", hint: "Polished business page", Preview: CompanyPreview },
];

const TOOLS: Array<{ href: string; icon: string; label: string }> = [
  { href: "/kudos/upload", icon: "📄", label: "Upload Doc" },
  { href: "/kudos/learn", icon: "🌐", label: "Teach Web" },
  { href: "/kudos/admin", icon: "⚙️", label: "Admin" },
  { href: "/kudos/guardian", icon: "🛡️", label: "Guardian" },
  { href: "/kudos/llm", icon: "✨", label: "LLM" },
  { href: "/kudos/agent", icon: "🤖", label: "Agent" },
  { href: "/kudos/archive", icon: "🕰️", label: "Archive" },
  { href: "/kudos/autolearn", icon: "🚀", label: "Auto-Learn" },
  { href: "/kudos/maps", icon: "🗺️", label: "Maps" },
  { href: "/kudos/networks", icon: "📡", label: "Networks" },
];

interface LauncherAction {
  icon: string;
  label: string;
  hint?: string;
  active?: boolean;
  onClick: () => void;
}

interface LauncherDockProps {
  onOpen: (kind: SiteKind) => void;
  actions?: LauncherAction[];
}

/**
 * Floating launcher dock — a pulsing yellow ✦ button (bottom-right) that
 * springs open a menu of one-click tools. Each maker row carries a live,
 * shimmering mini-preview of the page it will produce, so you can see what
 * you're launching before you click.
 */
export default function LauncherDock({ onOpen, actions = [] }: LauncherDockProps) {
  const [open, setOpen] = useState(false);

  const closeThen = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
      {open && (
        <div className="w-72 max-h-[70vh] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900/95 backdrop-blur p-2 shadow-2xl shadow-black/60">
          <p className="dock-pop text-[10px] font-bold uppercase tracking-widest text-amber-400 px-3 pt-2 pb-1">
            ⚡ Make something
          </p>
          {MAKERS.map((m, i) => (
            <button
              key={m.kind}
              onClick={() => {
                setOpen(false);
                onOpen(m.kind);
              }}
              style={{ animationDelay: `${60 + i * 70}ms` }}
              className="dock-pop w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm font-medium text-zinc-200 hover:bg-amber-500/15 hover:text-amber-300 hover:scale-[1.02] active:scale-[0.98] transition group"
            >
              <span className="icon-buzz text-xl w-8 text-center">{m.icon}</span>
              <span className="flex-1 min-w-0">
                <span className="block truncate">{m.label}</span>
                <span className="block text-[11px] font-normal text-zinc-500 group-hover:text-amber-400/80 truncate">
                  {m.hint}
                </span>
              </span>
              <span className="group-hover:rotate-12 transition-transform">
                <m.Preview />
              </span>
            </button>
          ))}
          <div className="border-t border-zinc-800 my-1.5" />
          <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 px-3 py-1">
            🧠 KUDOS tools
          </p>
          {TOOLS.map((t, i) => (
            <a
              key={t.href}
              href={t.href}
              style={{ animationDelay: `${200 + i * 25}ms` }}
              className="dock-pop w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 hover:translate-x-1 transition"
            >
              <span className="text-lg w-8 text-center">{t.icon}</span>
              {t.label}
            </a>
          ))}
          {actions.length > 0 && (
            <>
              <div className="border-t border-zinc-800 my-1.5" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 px-3 py-1">
                ✨ Actions
              </p>
              {actions.map((a, i) => (
                <button
                  key={a.label}
                  onClick={closeThen(a.onClick)}
                  style={{ animationDelay: `${200 + (TOOLS.length + i) * 25}ms` }}
                  className={`dock-pop w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left text-sm transition ${
                    a.active
                      ? "bg-amber-500/20 text-amber-300"
                      : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 hover:translate-x-1"
                  }`}
                >
                  <span className="text-lg w-8 text-center">{a.icon}</span>
                  <span className="flex-1 min-w-0">
                    {a.label}
                    {a.hint && (
                      <span className="block text-[11px] font-normal text-zinc-500 truncate">{a.hint}</span>
                    )}
                  </span>
                  {a.active && <span className="text-amber-400 text-xs">✓</span>}
                </button>
              ))}
            </>
          )}
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="dock-glow w-14 h-14 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 text-zinc-950 text-2xl shadow-xl hover:from-amber-300 hover:to-amber-500 active:scale-95 hover:scale-105 transition flex items-center justify-center"
        title={open ? "Close launcher" : "All KUDOS tools & features"}
        aria-label="Launch KUDOS tools"
      >
        <span className="spark-spin">{open ? "✕" : "✦"}</span>
      </button>
    </div>
  );
}