import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Course {
  id: number;
  code: string;
  title: string;
}
interface TimetableEntry {
  id: number;
  course_id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room: string;
  is_active: boolean;
  course: { id: number; code: string; title: string };
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function TimetablePage() {
  const [entries, setEntries] = useState<TimetableEntry[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [form, setForm] = useState({
    course_id: "",
    day_of_week: "0",
    start_time: "08:00",
    end_time: "09:00",
    room: "",
  });
  const [generateForm, setGenerateForm] = useState({
    start_date: "",
    end_date: "",
  });
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    const headers = getAuthHeader();
    const [ttRes, cRes] = await Promise.all([
      fetch("/api/v1/register/timetable", { headers }),
      fetch("/api/v1/courses/"),
    ]);
    if (ttRes.ok) setEntries(await ttRes.json());
    if (cRes.ok) setCourses(await cRes.json());
    setLoading(false);
  };

  const addEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ text: "", type: "" });
    const res = await fetch("/api/v1/register/timetable", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({
        course_id: parseInt(form.course_id),
        day_of_week: parseInt(form.day_of_week),
        start_time: form.start_time + ":00",
        end_time: form.end_time + ":00",
        room: form.room,
      }),
    });
    if (res.ok) {
      setMessage({ text: "✅ Timetable entry added!", type: "success" });
      setForm({ ...form, room: "" });
      fetchData();
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const deleteEntry = async (id: number) => {
    if (!confirm("Delete this timetable entry?")) return;
    await fetch(`/api/v1/register/timetable/${id}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    fetchData();
  };

  const generateSessions = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ text: "", type: "" });
    const res = await fetch("/api/v1/register/sessions/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({
        start_date: generateForm.start_date,
        end_date: generateForm.end_date,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({
        text: `✅ Generated ${data.sessions_created} sessions from ${data.start_date} to ${data.end_date}`,
        type: "success",
      });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const timeStr = (t: string) => t?.substring(0, 5);

  // Group by day
  const byDay = DAYS.map((day, i) => ({
    day,
    entries: entries.filter((e) => e.day_of_week === i),
  }));

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📅 Timetable Manager</h2>
      <p className="text-gray-600 mb-8">Define class schedules and auto-generate attendance sessions</p>

      {message.text && (
        <div
          className={`mb-6 p-3 rounded text-sm ${
            message.type === "success"
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-red-50 border border-red-200 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Add entry form */}
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold text-lg mb-4">Add Class</h3>
          <form onSubmit={addEntry} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Course</label>
              <select
                value={form.course_id}
                onChange={(e) => setForm({ ...form, course_id: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
                required
              >
                <option value="">Select course...</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Day</label>
              <select
                value={form.day_of_week}
                onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
              >
                {DAYS.map((d, i) => (
                  <option key={i} value={i}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1">Start</label>
                <input
                  type="time"
                  value={form.start_time}
                  onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                  className="w-full rounded border px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">End</label>
                <input
                  type="time"
                  value={form.end_time}
                  onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                  className="w-full rounded border px-3 py-2 text-sm"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Room</label>
              <input
                type="text"
                value={form.room}
                onChange={(e) => setForm({ ...form, room: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
                placeholder="e.g. Room 101"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-primary text-white py-2 rounded font-medium hover:bg-blue-800"
            >
              Add to Timetable
            </button>
          </form>

          {/* Generate sessions */}
          <hr className="my-6" />
          <h3 className="font-semibold text-lg mb-4">Generate Sessions</h3>
          <form onSubmit={generateSessions} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Start Date</label>
              <input
                type="date"
                value={generateForm.start_date}
                onChange={(e) =>
                  setGenerateForm({ ...generateForm, start_date: e.target.value })
                }
                className="w-full rounded border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">End Date</label>
              <input
                type="date"
                value={generateForm.end_date}
                onChange={(e) =>
                  setGenerateForm({ ...generateForm, end_date: e.target.value })
                }
                className="w-full rounded border px-3 py-2 text-sm"
                required
              />
            </div>
            <button
              type="submit"
              className="w-full bg-green-600 text-white py-2 rounded font-medium hover:bg-green-700"
            >
              ⚡ Auto-Generate Sessions
            </button>
            <p className="text-xs text-gray-400">
              Creates attendance sessions for every matching timetable entry in the date range.
              Skips dates that already have sessions.
            </p>
          </form>
        </div>

        {/* Weekly timetable view */}
        <div className="lg:col-span-2">
          <h3 className="font-semibold text-lg mb-4">Weekly Schedule</h3>
          {loading ? (
            <p className="text-gray-500">Loading...</p>
          ) : entries.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border">
              <p className="text-5xl mb-3">📭</p>
              <p className="text-gray-600">No timetable entries yet</p>
              <p className="text-sm text-gray-400 mt-1">Add a class using the form</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {byDay.map(
                ({ day, entries: dayEntries }) =>
                  dayEntries.length > 0 && (
                    <div key={day} className="bg-white rounded-xl border p-4">
                      <h4 className="font-semibold text-primary mb-3">{day}</h4>
                      <div className="space-y-2">
                        {dayEntries
                          .sort((a, b) => a.start_time.localeCompare(b.start_time))
                          .map((entry) => (
                            <div
                              key={entry.id}
                              className="p-3 bg-gray-50 rounded-lg text-sm relative group"
                            >
                              <p className="font-mono text-xs text-primary font-semibold">
                                {entry.course?.code}
                              </p>
                              <p className="font-medium">{entry.course?.title}</p>
                              <p className="text-gray-500 text-xs">
                                {timeStr(entry.start_time)} - {timeStr(entry.end_time)}
                                {entry.room && ` • ${entry.room}`}
                              </p>
                              <button
                                onClick={() => deleteEntry(entry.id)}
                                className="absolute top-2 right-2 text-xs text-red-400 opacity-0 group-hover:opacity-100 hover:text-red-600 transition"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                      </div>
                    </div>
                  )
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
