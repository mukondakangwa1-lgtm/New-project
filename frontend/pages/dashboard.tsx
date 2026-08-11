import { useState, useEffect } from "react";
import { getAuthHeader } from "@/lib/api";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";

interface Me {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  is_student: boolean;
  school: string | null;
}

interface ProgressItem {
  id: number;
  content_key: string;
  kind: string;
  title: string;
  url: string;
  position_pct: number;
  detail: string;
  source: string;
  updated_at: string;
}

interface CalendarEvent {
  id: number;
  title: string;
  description?: string;
  event_type?: string;
  start_time: string;
  end_time: string;
  location?: string;
}

interface Goal {
  id: number;
  title: string;
  description?: string;
  goal_type?: string;
  target_value: number;
  current_value: number;
  deadline: string | null;
  is_completed?: boolean;
}

const KIND_ICONS: Record<string, string> = {
  movie: "🎬",
  book: "📖",
  audio: "🎵",
  document: "📄",
};

export default function Dashboard() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [progress, setProgress] = useState<ProgressItem[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [convCount, setConvCount] = useState<number | null>(null);
  const [devicesCount, setDevicesCount] = useState<number | null>(null);
  const [newEventTitle, setNewEventTitle] = useState("");
  const [newEventStart, setNewEventStart] = useState("");
  const [newEventEnd, setNewEventEnd] = useState("");
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/v1/users/me", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((u: Me) => {
        setMe(u);
        return u;
      })
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!me) return;
    // Continue where you left off
    fetch("/api/v1/progress/recent", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : []))
      .then(setProgress)
      .catch(() => setProgress([]));
    // Smart calendar — upcoming events
    const start = new Date().toISOString();
    const end = new Date(Date.now() + 90 * 86400000).toISOString();
    fetch(`/api/v1/planner/calendar?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`, {
      headers: getAuthHeader(),
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setEvents(Array.isArray(d) ? d : []))
      .catch(() => setEvents([]));
    // Smart todo list — study goals
    fetch("/api/v1/planner/goals", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setGoals(Array.isArray(d) ? d : []))
      .catch(() => setGoals([]));
    // Stats
    fetch("/api/v1/kudos/conversations", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setConvCount(Array.isArray(d) ? d.length : null))
      .catch(() => setConvCount(null));
    fetch("/api/v1/kudos/devices", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setDevicesCount(Array.isArray(d) ? d.length : null))
      .catch(() => setDevicesCount(null));
  }, [me]);

  const addEvent = async () => {
    if (!newEventTitle.trim() || !newEventStart || !newEventEnd) return;
    try {
      const res = await fetch("/api/v1/planner/calendar", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ title: newEventTitle, start_time: newEventStart, end_time: newEventEnd }),
      });
      if (res.ok) {
        setNewEventTitle("");
        setNewEventStart("");
        setNewEventEnd("");
        setMsg("Event added to your smart calendar.");
        setEvents([]);
        fetch("/api/v1/planner/calendar", { headers: getAuthHeader() })
          .then((r) => (r.ok ? r.json() : []))
          .then((d) => setEvents(Array.isArray(d) ? d : []))
          .catch(() => {});
      }
    } catch {}
  };

  const addGoal = async () => {
    if (!newGoalTitle.trim()) return;
    try {
      const res = await fetch("/api/v1/planner/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ title: newGoalTitle, goal_type: "todo" }),
      });
      if (res.ok) {
        setNewGoalTitle("");
        setMsg("Added to your smart todo list.");
        fetch("/api/v1/planner/goals", { headers: getAuthHeader() })
          .then((r) => (r.ok ? r.json() : []))
          .then((d) => setGoals(Array.isArray(d) ? d : []))
          .catch(() => {});
      }
    } catch {}
  };

  const bumpGoal = async (id: number, inc = 1) => {
    await fetch(`/api/v1/planner/goals/${id}?increment=${inc}`, { method: "PATCH", headers: getAuthHeader() });
    fetch("/api/v1/planner/goals", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setGoals(Array.isArray(d) ? d : []))
      .catch(() => {});
  };

  const clearProgress = async (key: string) => {
    await fetch(`/api/v1/progress/${encodeURIComponent(key)}`, { method: "DELETE", headers: getAuthHeader() });
    setProgress((p) => p.filter((i) => i.content_key !== key));
  };

  const fmtDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };

  const dueGoals = goals.filter((g) => !g.is_completed).sort((a, b) => {
    if (!a.deadline) return 1;
    if (!b.deadline) return -1;
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
  });

  return (
    <RequireRole roles={["user", "student", "admin"]} redirectTo="/kudos">
      <Layout>
        <h2 className="text-3xl font-bold mb-2">📊 Dashboard</h2>
        <p className="text-gray-600 mb-6">Welcome back, {me?.full_name || "friend"}!</p>

        {msg && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-green-50 text-green-700 text-sm border border-green-200">
            {msg}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <div className="text-2xl font-bold text-gray-800">{convCount ?? "—"}</div>
            <div className="text-xs text-gray-400 uppercase mt-1">KUDOS projects</div>
          </div>
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <div className="text-2xl font-bold text-gray-800">{devicesCount ?? "—"}</div>
            <div className="text-xs text-gray-400 uppercase mt-1">KUDOS devices</div>
          </div>
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <div className="text-2xl font-bold text-gray-800">{progress.length}</div>
            <div className="text-xs text-gray-400 uppercase mt-1">In progress</div>
          </div>
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <div className="text-2xl font-bold text-gray-800">{dueGoals.length}</div>
            <div className="text-xs text-gray-400 uppercase mt-1">Open todos</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Continue where you left off */}
          <div className="bg-white border rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-lg mb-4">🎬 Continue where you left off</h3>
            {progress.length === 0 ? (
              <p className="text-sm text-gray-400">
                Nothing yet — when you start a movie, book or track from the Media or Library pages, it shows up
                here so you can pick up right where you stopped.
              </p>
            ) : (
              <div className="space-y-3">
                {progress.map((item) => (
                  <div key={item.id} className="flex items-center gap-3 border rounded-lg p-3 hover:bg-gray-50">
                    <span className="text-2xl">{KIND_ICONS[item.kind] || "📎"}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{item.title || item.content_key}</p>
                      <p className="text-xs text-gray-400">
                        {item.detail || `${Math.round(item.position_pct || 0)}% done`} • {fmtDate(item.updated_at)}
                      </p>
                      <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                        <div
                          className="bg-primary h-1.5 rounded-full"
                          style={{ width: `${Math.min(100, Math.max(2, item.position_pct || 0))}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary font-medium hover:underline"
                        >
                          Resume →
                        </a>
                      )}
                      <button onClick={() => clearProgress(item.content_key)} className="text-xs text-gray-400 hover:text-red-600">
                        Clear
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Smart todo list */}
          <div className="bg-white border rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-lg mb-4">✅ Smart Todo List</h3>
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={newGoalTitle}
                onChange={(e) => setNewGoalTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addGoal()}
                placeholder="Add a todo..."
                className="flex-1 rounded border px-3 py-2 text-sm"
              />
              <button
                onClick={addGoal}
                className="bg-primary text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-800"
              >
                Add
              </button>
            </div>
            {dueGoals.length === 0 ? (
              <p className="text-sm text-gray-400">No open todos. Enjoy the calm! 🏖️</p>
            ) : (
              <ul className="space-y-2">
                {dueGoals.map((goal) => (
                  <li key={goal.id} className="flex items-center gap-3 border rounded-lg p-3">
                    <button
                      onClick={() => bumpGoal(goal.id, goal.target_value)}
                      className="w-5 h-5 rounded border border-gray-300 hover:bg-green-100"
                      title="Mark done"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{goal.title}</p>
                      <p className="text-xs text-gray-400">
                        {goal.current_value}/{goal.target_value}
                        {goal.deadline && ` • due ${fmtDate(goal.deadline)}`}
                      </p>
                    </div>
                    {goal.deadline && (
                      <span className="text-xs text-gray-400">
                        {new Date(goal.deadline).getTime() - Date.now() < 86400000 * 3 ? "🔥" : ""}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Smart calendar */}
        <div className="bg-white border rounded-xl shadow-sm p-6 mb-8">
          <h3 className="font-semibold text-lg mb-4">📅 Smart Calendar</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-6">
            <input
              type="text"
              value={newEventTitle}
              onChange={(e) => setNewEventTitle(e.target.value)}
              placeholder="Event title"
              className="rounded border px-3 py-2 text-sm"
            />
            <input
              type="datetime-local"
              value={newEventStart}
              onChange={(e) => setNewEventStart(e.target.value)}
              className="rounded border px-3 py-2 text-sm"
            />
            <input
              type="datetime-local"
              value={newEventEnd}
              onChange={(e) => setNewEventEnd(e.target.value)}
              className="rounded border px-3 py-2 text-sm"
            />
            <button
              onClick={addEvent}
              disabled={!newEventTitle || !newEventStart}
              className="bg-primary text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-800 disabled:opacity-50"
            >
              + Add
            </button>
          </div>
          {events.length === 0 ? (
            <p className="text-sm text-gray-400">No upcoming events.</p>
          ) : (
            <div className="space-y-2">
              {events.map((ev) => (
                <div key={ev.id} className="flex items-center gap-4 border rounded-lg p-3">
                  <div className="w-16 text-center">
                    <p className="text-lg font-bold text-primary">{fmtDate(ev.start_time)}</p>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{ev.title}</p>
                    {ev.location && <p className="text-xs text-gray-400">📍 {ev.location}</p>}
                  </div>
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                    {ev.event_type || "event"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/kudos" className="bg-white border rounded-xl p-6 hover:shadow-lg transition block">
            <h3 className="font-semibold text-lg mb-1">🧠 Ask KUDOS</h3>
            <p className="text-sm text-gray-500">Your assistant, with your history.</p>
          </Link>
          <Link href="/media" className="bg-white border rounded-xl p-6 hover:shadow-lg transition block">
            <h3 className="font-semibold text-lg mb-1">🎬 Media</h3>
            <p className="text-sm text-gray-500">Movies, TV, music and more.</p>
          </Link>
          <Link href="/library" className="bg-white border rounded-xl p-6 hover:shadow-lg transition block">
            <h3 className="font-semibold text-lg mb-1">📚 Library</h3>
            <p className="text-sm text-gray-500">Search the ordered collection.</p>
          </Link>
        </div>
      </Layout>
    </RequireRole>
  );
}
