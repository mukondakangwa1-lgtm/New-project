export default function Custom404() {
  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-8 text-center">
      <div className="w-20 h-20 rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center text-4xl animate-pulse mb-6">
        🧠
      </div>
      <h1 className="text-2xl md:text-3xl font-bold text-zinc-50 max-w-2xl leading-snug">
        KUDOS is temporarily undergoing maintenance
        <span className="text-amber-400">, we will be back shortly.</span>
      </h1>
      <p className="text-zinc-500 text-sm mt-4 max-w-md">
        Our team is working hard to get everything back online.
      </p>
      <div className="mt-8 flex gap-3">
        <a
          href="/"
          className="px-5 py-2.5 rounded-lg bg-amber-500 text-zinc-950 text-sm font-semibold hover:bg-amber-400 transition"
        >
          Try again
        </a>
        <a
          href="/kudos"
          className="px-5 py-2.5 rounded-lg border border-zinc-700 text-zinc-300 text-sm font-medium hover:bg-zinc-900 transition"
        >
          Back to chat
        </a>
      </div>
    </main>
  );
}