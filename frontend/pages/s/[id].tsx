import { useRouter } from "next/router";
import { useState } from "react";

/**
 * Public, smooth site link — /s/{id}.
 *
 * Anyone (registered or not) can open one of these links and see the launched
 * site instantly, full-bleed, with no app chrome. The generated site is served
 * from the public API inside an iframe; the chrome link always drops the user
 * back into KUDOS, which shows the public chat for unregistered visitors.
 */
function isValidId(id: string) {
  return /^[a-f0-9]{12}$/.test(id);
}

export default function PublicSite() {
  const router = useRouter();
  const id = String(router.query.id || "");
  const valid = isValidId(id);
  const siteUrl = valid ? `/api/v1/kudos/sites/${id}/` : "";
  const [loaded, setLoaded] = useState(false);

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Slim brand bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 bg-zinc-950 text-sm text-zinc-200">
        <span className="font-semibold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          KUDOS · Live site
        </span>
        <a
          href="/kudos"
          className="px-3 py-1.5 rounded-lg bg-amber-500 text-zinc-950 text-xs font-semibold hover:bg-amber-400 transition"
        >
          💬 Chat with KUDOS
        </a>
      </div>

      {!valid ? (
        <div className="flex-1 grid place-items-center p-8 text-center">
          <div>
            <p className="text-5xl mb-3">🔗</p>
            <p className="text-zinc-300 font-medium mb-1">This is not a KUDOS site link.</p>
            <p className="text-zinc-500 text-sm mb-5">Check the link and try again.</p>
            <a href="/kudos" className="text-amber-400 hover:text-amber-300 text-sm font-medium">
              💬 Head to the KUDOS chat
            </a>
          </div>
        </div>
      ) : (
        <div className="relative flex-1 bg-white">
          {!loaded && (
            <div className="absolute inset-0 grid place-items-center text-zinc-400 text-sm">
              Loading live site…
            </div>
          )}
          <iframe
            src={siteUrl}
            title="KUDOS live site"
            className={`w-full h-full border-0 ${loaded ? "" : "invisible"}`}
            onLoad={() => setLoaded(true)}
          />
        </div>
      )}
    </div>
  );
}