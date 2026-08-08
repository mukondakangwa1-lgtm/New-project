import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

interface Course {
  id: number;
  title: string;
  code: string;
  description: string;
  instructor: string;
  credits: number;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function Courses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newCourse, setNewCourse] = useState({ title: "", code: "", description: "", instructor: "", credits: 3 });

  const fetchCourses = () => {
    fetch("/api/v1/courses/")
      .then((r) => r.json())
      .then((data) => {
        setCourses(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchCourses();
  }, []);

  const enroll = async (courseId: number) => {
    setEnrolling(courseId);
    setMsg("");
    try {
      const res = await fetch(`/api/v1/courses/${courseId}/enroll`, {
        method: "POST",
        headers: { ...getAuthHeader() },
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Enroll failed - login required");
      }
      setMsg("✅ Enrolled successfully - see Dashboard");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    } finally {
      setEnrolling(null);
    }
  };

  const createCourse = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      const res = await fetch("/api/v1/courses/", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify(newCourse),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Create failed - admin only");
      }
      setNewCourse({ title: "", code: "", description: "", instructor: "", credits: 3 });
      setShowCreate(false);
      fetchCourses();
      setMsg("✅ Course created");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold">📚 Courses</h2>
        <button onClick={() => setShowCreate(!showCreate)} className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-800">
          {showCreate ? "Close" : "+ New Course (Admin)"}
        </button>
      </div>

      {msg && <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith("✅") ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>{msg}</div>}

      {showCreate && (
        <form onSubmit={createCourse} className="bg-white rounded-xl border shadow p-6 mb-6 space-y-4">
          <h3 className="font-semibold">Create Course (Admin only, uses PostgreSQL/SQLite)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input type="text" value={newCourse.title} onChange={(e) => setNewCourse({ ...newCourse, title: e.target.value })} placeholder="Title e.g. Data Structures" className="rounded border px-3 py-2 text-sm" required />
            <input type="text" value={newCourse.code} onChange={(e) => setNewCourse({ ...newCourse, code: e.target.value })} placeholder="Code e.g. CS201" className="rounded border px-3 py-2 text-sm" required />
            <input type="text" value={newCourse.instructor} onChange={(e) => setNewCourse({ ...newCourse, instructor: e.target.value })} placeholder="Instructor" className="rounded border px-3 py-2 text-sm" />
            <input type="number" value={newCourse.credits} onChange={(e) => setNewCourse({ ...newCourse, credits: Number(e.target.value) })} placeholder="Credits" className="rounded border px-3 py-2 text-sm" min={1} max={6} />
          </div>
          <textarea value={newCourse.description} onChange={(e) => setNewCourse({ ...newCourse, description: e.target.value })} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
          <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg text-sm font-medium">Create</button>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading courses...</p>
      ) : courses.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border shadow">
          <p className="text-5xl mb-4">📭</p>
          <p className="text-xl text-gray-600 mb-2">No courses yet</p>
          <p className="text-gray-500">Run: <code className="bg-gray-100 px-2 py-1 rounded">python seed.py</code> or create one above (admin).</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course) => (
            <div key={course.id} className="rounded-xl bg-white p-6 shadow border hover:shadow-lg transition flex flex-col">
              <div className="flex justify-between items-start mb-3">
                <span className="text-xs font-mono bg-primary text-white px-2 py-1 rounded">{course.code}</span>
                <span className="text-xs text-gray-500">{course.credits} credits</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">{course.title}</h3>
              {course.description && <p className="text-sm text-gray-600 mb-3 flex-1">{course.description}</p>}
              {course.instructor && <p className="text-sm text-gray-500 mb-4">👤 {course.instructor}</p>}
              <button onClick={() => enroll(course.id)} disabled={enrolling === course.id} className="w-full bg-primary text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-800 disabled:opacity-50">
                {enrolling === course.id ? "Enrolling..." : "Enroll"}
              </button>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
