import { useState, useEffect } from "react";
import { getAuthHeader } from "@/lib/api";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";

interface Course {
  id: number;
  code: string;
  title: string;
  description: string;
  instructor: string;
  credits: number;
}
interface Assignment {
  id: number;
  course_id: number;
  title: string;
  description?: string;
  due_date: string | null;
  max_score: number;
  course?: { code: string; title: string };
}
interface Attendance {
  id: number;
  session_id: number;
  status: string;
  checked_in_at: string;
  session?: { course_id: number; session_date: string; start_time: string; course?: { code: string; title: string } };
}
interface TimetableEntry {
  id: number;
  course_id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room: string;
  course: { code: string; title: string };
}
interface CalendarEvent {
  id: number;
  title: string;
  event_type?: string;
  start_time: string;
  location?: string;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATUS_COLORS: Record<string, string> = {
  present: "bg-green-100 text-green-700",
  late: "bg-yellow-100 text-yellow-700",
  excused: "bg-blue-100 text-blue-700",
  absent: "bg-red-100 text-red-700",
};

export default function StudentAcademics() {
  const router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [attendance, setAttendance] = useState<Attendance[]>([]);
  const [timetable, setTimetable] = useState<TimetableEntry[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "assignments" | "attendance" | "calendar">("overview");

  useEffect(() => {
    fetch("/api/v1/users/me", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((u) => setMe(u))
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!me?.is_student) return;
    const headers = getAuthHeader();
    Promise.all([
      fetch("/api/v1/courses/", { headers }).then((r) => (r.ok ? r.json() : [])),
      fetch("/api/v1/academic/assignments", { headers }).then((r) => (r.ok ? r.json() : [])),
      fetch("/api/v1/register/attendance/my", { headers }).then((r) => (r.ok ? r.json() : [])),
      fetch("/api/v1/register/timetable", { headers }).then((r) => (r.ok ? r.json() : [])),
      fetch("/api/v1/planner/calendar", { headers }).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([c, a, att, tt, ev]) => {
        setCourses(Array.isArray(c) ? c : []);
        setAssignments(Array.isArray(a) ? a : []);
        setAttendance(Array.isArray(att) ? att : []);
        setTimetable(Array.isArray(tt) ? tt : []);
        setEvents(Array.isArray(ev) ? ev : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [me]);

  if (loading || !me) {
    return (
      <RequireRole roles={["student"]} redirectTo="/dashboard">
        <Layout>
          <p className="text-gray-500">Loading your academic hub...</p>
        </Layout>
      </RequireRole>
    );
  }

  if (!me.is_student) {
    return (
      <Layout>
        <div className="text-center py-16">
          <p className="text-6xl mb-4">🎓</p>
          <h2 className="text-2xl font-bold mb-2">Students Only</h2>
          <p className="text-gray-600 mb-6">
            Courses &amp; Register are reserved for approved students.
          </p>
          <Link href="/dashboard" className="bg-primary text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-800 inline-block">
            Back to Dashboard
          </Link>
        </div>
      </Layout>
    );
  }

  // Smart study timetable: today's classes + assignments due within 7 days
  const todayIdx = (new Date().getDay() + 6) % 7; // Mon=0
  const todayClasses = timetable.filter((t) => t.day_of_week === todayIdx);
  const soon = assignments
    .filter((a) => a.due_date && new Date(a.due_date).getTime() - Date.now() < 7 * 86400000)
    .sort((a, b) => (a.due_date! < b.due_date! ? -1 : 1));

  const fmtDay = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };
  const timeStr = (t?: string) => t?.substring(0, 5) || "";

  return (
    <RequireRole roles={["student"]} redirectTo="/dashboard">
      <Layout>
        <h2 className="text-3xl font-bold mb-2">🎓 Courses &amp; Register</h2>
        <p className="text-gray-600 mb-6">
          {me.school ? `🏫 ${me.school}` : "Student"} — attendance, assignments, calendar &amp; your smart study plan
        </p>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {[
            { id: "overview" as const, label: "📊 Overview" },
            { id: "assignments" as const, label: "📝 Assignments" },
            { id: "attendance" as const, label: "✅ Attendance" },
            { id: "calendar" as const, label: "📅 Calendar" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                tab === t.id ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "overview" && (
          <div className="space-y-6">
            {/* Quick stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white border rounded-xl p-5 shadow-sm">
                <div className="text-2xl font-bold text-gray-800">{courses.length}</div>
                <div className="text-xs text-gray-400 uppercase mt-1">Courses</div>
              </div>
              <div className="bg-white border rounded-xl p-5 shadow-sm">
                <div className="text-2xl font-bold text-gray-800">{assignments.length}</div>
                <div className="text-xs text-gray-400 uppercase mt-1">Assignments</div>
              </div>
              <div className="bg-white border rounded-xl p-5 shadow-sm">
                <div className="text-2xl font-bold text-gray-800">{attendance.length}</div>
                <div className="text-xs text-gray-400 uppercase mt-1">Check-ins</div>
              </div>
              <div className="bg-white border rounded-xl p-5 shadow-sm">
                <div className="text-2xl font-bold text-gray-800">{soon.length}</div>
                <div className="text-xs text-gray-400 uppercase mt-1">Due this week</div>
              </div>
            </div>

            {/* Smart study plan */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white border rounded-xl shadow-sm p-6">
                <h3 className="font-semibold text-lg mb-4">🧠 Smart Study Timetable</h3>
                <p className="text-xs text-gray-400 mb-3">
                  Today is {DAYS[todayIdx]} — {todayClasses.length} class{todayClasses.length === 1 ? "" : "es"}
                </p>
                {todayClasses.length === 0 && soon.length === 0 ? (
                  <p className="text-sm text-gray-400">No classes or deadlines today. Enjoy the break! 🎉</p>
                ) : (
                  <div className="space-y-3">
                    {todayClasses.map((entry) => (
                      <div key={entry.id} className="border rounded-lg p-3 flex items-center gap-3">
                        <span className="text-2xl">🏫</span>
                        <div className="flex-1">
                          <p className="text-sm font-medium">{entry.course?.title}</p>
                          <p className="text-xs text-gray-400">
                            {timeStr(entry.start_time)} - {timeStr(entry.end_time)}
                            {entry.room && ` • ${entry.room}`}
                          </p>
                        </div>
                        <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded font-mono">
                          {entry.course?.code}
                        </span>
                      </div>
                    ))}
                    {soon.map((a) => (
                      <div key={a.id} className="border rounded-lg p-3 flex items-center gap-3 border-amber-200 bg-amber-50">
                        <span className="text-2xl">⏰</span>
                        <div className="flex-1">
                          <p className="text-sm font-medium">{a.title}</p>
                          <p className="text-xs text-gray-400">due {fmtDay(a.due_date!)}</p>
                        </div>
                        <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">
                          {a.course?.code || "Assignment"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Attendance summary */}
              <div className="bg-white border rounded-xl shadow-sm p-6">
                <h3 className="font-semibold text-lg mb-4">✅ Attendance at a glance</h3>
                {attendance.length === 0 ? (
                  <p className="text-sm text-gray-400">
                    No check-ins recorded yet. Check in from the Attendance tab when a session is open.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {attendance.slice().reverse().slice(0, 8).map((att) => (
                      <div key={att.id} className="flex items-center justify-between border-b pb-2 text-sm">
                        <span className="text-gray-600">
                          {att.session?.course?.code || `Session ${att.session_id}`}
                        </span>
                        <span className="text-xs text-gray-400">
                          {att.session?.session_date ? fmtDay(att.session.session_date) : ""}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[att.status] || "bg-gray-100"}`}>
                          {att.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === "assignments" && (
          <div>
            {assignments.length === 0 ? (
              <div className="text-center py-16 bg-white rounded-xl border">
                <p className="text-5xl mb-3">📝</p>
                <p className="text-gray-600">No assignments yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {assignments.map((a) => (
                  <div key={a.id} className="bg-white border rounded-xl p-5 shadow hover:shadow-lg transition">
                    <span className="text-xs font-mono bg-primary text-white px-2 py-1 rounded">
                      {a.course?.code || "Assignment"}
                    </span>
                    <h3 className="font-semibold text-lg mt-2 mb-1">{a.title}</h3>
                    {a.description && <p className="text-sm text-gray-500 mb-2 line-clamp-2">{a.description}</p>}
                    <div className="flex justify-between text-xs text-gray-400 mt-3">
                      <span>Max {a.max_score}</span>
                      {a.due_date ? (
                        <span className={new Date(a.due_date).getTime() - Date.now() < 3 * 86400000 ? "text-red-500 font-medium" : ""}>
                          due {fmtDay(a.due_date)}
                        </span>
                      ) : (
                        <span>no due date</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "attendance" && (
          <div className="bg-white border rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-lg mb-4">✅ My Attendance</h3>
            {attendance.length === 0 ? (
              <p className="text-sm text-gray-400">
                No check-ins yet. When a session is open you can check in on the{" "}
                <Link href="/register/attendance" className="text-primary underline">Register page</Link>.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-gray-600">
                  <tr>
                    <th className="px-4 py-3">Course</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {attendance.slice().reverse().map((att) => (
                    <tr key={att.id} className="border-t">
                      <td className="px-4 py-3 font-medium">{att.session?.course?.code || `Session ${att.session_id}`}</td>
                      <td className="px-4 py-3 text-gray-500">{att.session?.session_date}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[att.status] || "bg-gray-100"}`}>
                          {att.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {att.checked_in_at ? new Date(att.checked_in_at).toLocaleTimeString() : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="mt-6">
              <Link href="/register/attendance" className="text-primary text-sm font-medium hover:underline">
                Open Register → Check in for today&apos;s sessions
              </Link>
            </div>
          </div>
        )}

        {tab === "calendar" && (
          <div className="bg-white border rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-lg mb-4">📅 Programs on Calendar</h3>
            {events.length === 0 ? (
              <p className="text-sm text-gray-400">No calendar events yet. Add one from your Dashboard.</p>
            ) : (
              <div className="space-y-2">
                {events
                  .slice()
                  .sort((a, b) => a.start_time.localeCompare(b.start_time))
                  .map((ev) => (
                    <div key={ev.id} className="flex items-center gap-4 border rounded-lg p-3">
                      <div className="w-16 text-center">
                        <p className="text-lg font-bold text-primary">{fmtDay(ev.start_time)}</p>
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
        )}
      </Layout>
    </RequireRole>
  );
}
