import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Session {
  id: number;
  course_id: number;
  session_date: string;
  start_time: string;
  end_time: string;
  room: string;
  is_open: boolean;
  is_cancelled: boolean;
  course: { id: number; code: string; title: string; instructor: string };
}

interface Attendance {
  id: number;
  session_id: number;
  student_id: number;
  checked_in_at: string;
  status: string;
  student: { id: number; full_name: string; email: string };
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AttendanceRegister() {
  const [todaySessions, setTodaySessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [attendances, setAttendances] = useState<Attendance[]>([]);
  const [checkInSessionId, setCheckInSessionId] = useState("");
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTodaySessions();
  }, []);

  const fetchTodaySessions = async () => {
    try {
      const res = await fetch("/api/v1/register/sessions/today", {
        headers: getAuthHeader(),
      });
      if (res.ok) {
        const data = await res.json();
        setTodaySessions(data);
      }
    } catch (e) {}
    setLoading(false);
  };

  const fetchSessionAttendance = async (session: Session) => {
    setSelectedSession(session);
    try {
      const res = await fetch(
        `/api/v1/register/attendance/session/${session.id}`,
        { headers: getAuthHeader() }
      );
      if (res.ok) {
        setAttendances(await res.json());
      }
    } catch (e) {}
  };

  const toggleSession = async (session: Session) => {
    const res = await fetch(`/api/v1/register/sessions/${session.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ is_open: !session.is_open }),
    });
    if (res.ok) {
      setMessage({
        text: `Session ${!session.is_open ? "opened" : "closed"} for check-in`,
        type: "success",
      });
      fetchTodaySessions();
      if (selectedSession?.id === session.id) {
        fetchSessionAttendance({ ...session, is_open: !session.is_open });
      }
    }
  };

  const handleCheckIn = async () => {
    if (!checkInSessionId) return;
    setMessage({ text: "", type: "" });

    const res = await fetch("/api/v1/register/attendance/check-in", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ session_id: parseInt(checkInSessionId), status: "present" }),
    });

    if (res.ok) {
      setMessage({ text: "✅ Checked in successfully!", type: "success" });
      setCheckInSessionId("");
      if (selectedSession) fetchSessionAttendance(selectedSession);
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const markAttendance = async (sessionId: number, studentId: number, status: string) => {
    const res = await fetch(`/api/v1/register/attendance/session/${sessionId}/mark`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ student_id: studentId, status }),
    });
    if (res.ok && selectedSession) {
      fetchSessionAttendance(selectedSession);
    }
  };

  const timeStr = (t: string) => t?.substring(0, 5);

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📋 Digital Register</h2>
      <p className="text-gray-600 mb-8">Today&apos;s attendance sessions</p>

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

      {/* Student check-in */}
      <div className="mb-8 p-4 bg-white rounded-xl border shadow">
        <h3 className="font-semibold mb-3">Student Check-In</h3>
        <div className="flex gap-3">
          <select
            value={checkInSessionId}
            onChange={(e) => setCheckInSessionId(e.target.value)}
            className="flex-1 rounded border px-3 py-2 text-sm"
          >
            <option value="">Select an open session...</option>
            {todaySessions
              .filter((s) => s.is_open && !s.is_cancelled)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.course.code} — {timeStr(s.start_time)}-{timeStr(s.end_time)} ({s.room})
                </option>
              ))}
          </select>
          <button
            onClick={handleCheckIn}
            disabled={!checkInSessionId}
            className="bg-green-600 text-white px-6 py-2 rounded font-medium hover:bg-green-700 disabled:opacity-50"
          >
            Check In
          </button>
        </div>
      </div>

      {/* Today's sessions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="font-semibold text-lg mb-4">
            Today&apos;s Sessions ({todaySessions.length})
          </h3>
          {loading ? (
            <p className="text-gray-500">Loading...</p>
          ) : todaySessions.length === 0 ? (
            <div className="text-center py-8 bg-white rounded-xl border">
              <p className="text-4xl mb-2">📅</p>
              <p className="text-gray-600">No sessions scheduled for today</p>
              <p className="text-sm text-gray-400 mt-1">
                Generate sessions from the Timetable page
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {todaySessions.map((session) => (
                <div
                  key={session.id}
                  className={`p-4 bg-white rounded-lg border cursor-pointer transition hover:shadow ${
                    selectedSession?.id === session.id ? "ring-2 ring-primary" : ""
                  } ${session.is_cancelled ? "opacity-50" : ""}`}
                  onClick={() => fetchSessionAttendance(session)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-mono text-xs bg-primary text-white px-2 py-0.5 rounded">
                        {session.course.code}
                      </span>
                      <h4 className="font-medium mt-1">{session.course.title}</h4>
                      <p className="text-sm text-gray-500">
                        {timeStr(session.start_time)} - {timeStr(session.end_time)} • {session.room}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {session.is_cancelled ? (
                        <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">Cancelled</span>
                      ) : session.is_open ? (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded animate-pulse">
                          ● Open
                        </span>
                      ) : (
                        <span className="text-xs bg-gray-100 text-gray-500 px-2 py-1 rounded">Closed</span>
                      )}
                      {!session.is_cancelled && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSession(session);
                          }}
                          className={`text-xs px-3 py-1 rounded font-medium ${
                            session.is_open
                              ? "bg-red-100 text-red-700 hover:bg-red-200"
                              : "bg-green-100 text-green-700 hover:bg-green-200"
                          }`}
                        >
                          {session.is_open ? "Close" : "Open"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Attendance list for selected session */}
        <div>
          <h3 className="font-semibold text-lg mb-4">
            {selectedSession
              ? `Attendance — ${selectedSession.course.code} (${selectedSession.session_date})`
              : "Select a session to view attendance"}
          </h3>
          {selectedSession && (
            <div className="bg-white rounded-xl border">
              {attendances.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-3xl mb-2">📝</p>
                  <p>No check-ins yet</p>
                  {selectedSession.is_open && (
                    <p className="text-sm text-green-600 mt-1">Session is open — waiting for students</p>
                  )}
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 text-left">
                    <tr>
                      <th className="px-4 py-3">Student</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Time</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attendances.map((att) => (
                      <tr key={att.id} className="border-t">
                        <td className="px-4 py-3">
                          <p className="font-medium">{att.student?.full_name}</p>
                          <p className="text-xs text-gray-400">{att.student?.email}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`text-xs px-2 py-1 rounded ${
                              att.status === "present"
                                ? "bg-green-100 text-green-700"
                                : att.status === "late"
                                ? "bg-yellow-100 text-yellow-700"
                                : att.status === "excused"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {att.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {new Date(att.checked_in_at).toLocaleTimeString()}
                        </td>
                        <td className="px-4 py-3">
                          <select
                            value={att.status}
                            onChange={(e) =>
                              markAttendance(selectedSession.id, att.student_id, e.target.value)
                            }
                            className="text-xs border rounded px-2 py-1"
                          >
                            <option value="present">Present</option>
                            <option value="late">Late</option>
                            <option value="absent">Absent</option>
                            <option value="excused">Excused</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
