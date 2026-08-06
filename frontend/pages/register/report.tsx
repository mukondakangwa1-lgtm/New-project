import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Course {
  id: number;
  code: string;
  title: string;
}
interface ReportRow {
  student: { id: number; full_name: string; email: string };
  course: { id: number; code: string; title: string };
  total_sessions: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  attendance_rate: number;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AttendanceReport() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [report, setReport] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/v1/courses/")
      .then((r) => r.json())
      .then(setCourses);
  }, []);

  const fetchReport = async (courseId: string) => {
    setSelectedCourse(courseId);
    if (!courseId) {
      setReport([]);
      return;
    }
    setLoading(true);
    const res = await fetch(`/api/v1/register/attendance/report/${courseId}`, {
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setReport(await res.json());
    }
    setLoading(false);
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📊 Attendance Report</h2>
      <p className="text-gray-600 mb-8">View attendance statistics per student per course</p>

      <div className="mb-6">
        <select
          value={selectedCourse}
          onChange={(e) => fetchReport(e.target.value)}
          className="rounded border px-4 py-2 text-sm min-w-[300px]"
        >
          <option value="">Select a course...</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.title}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading report...</p>
      ) : !selectedCourse ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <p className="text-5xl mb-3">📊</p>
          <p className="text-gray-600">Select a course to view attendance report</p>
        </div>
      ) : report.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <p className="text-5xl mb-3">📭</p>
          <p className="text-gray-600">No enrolled students or sessions yet</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3 text-center">Sessions</th>
                <th className="px-4 py-3 text-center">Present</th>
                <th className="px-4 py-3 text-center">Late</th>
                <th className="px-4 py-3 text-center">Absent</th>
                <th className="px-4 py-3 text-center">Excused</th>
                <th className="px-4 py-3 text-center">Rate</th>
              </tr>
            </thead>
            <tbody>
              {report.map((row) => (
                <tr key={row.student.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium">{row.student.full_name}</p>
                    <p className="text-xs text-gray-400">{row.student.email}</p>
                  </td>
                  <td className="px-4 py-3 text-center font-mono">{row.total_sessions}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">
                      {row.present}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded text-xs">
                      {row.late}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs">
                      {row.absent}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">
                      {row.excused}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center gap-2 justify-center">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            row.attendance_rate >= 80
                              ? "bg-green-500"
                              : row.attendance_rate >= 60
                              ? "bg-yellow-500"
                              : "bg-red-500"
                          }`}
                          style={{ width: `${row.attendance_rate}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs font-semibold">
                        {row.attendance_rate}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
