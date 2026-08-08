import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

function auth(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function Assignments() {
  const [assignments, setAssignments] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ course_id: "", title: "", description: "", max_score: 100 });
  const [submitContent, setSubmitContent] = useState<Record<number, string>>({});

  const load = () => {
    fetch("/api/v1/academic/assignments", { headers: auth() })
      .then((r) => r.json())
      .then((d) => setAssignments(Array.isArray(d) ? d : []))
      .catch(() => setAssignments([]))
      .finally(() => setLoading(false));
    fetch("/api/v1/courses/")
      .then((r) => r.json())
      .then((d) => setCourses(Array.isArray(d) ? d : []))
      .catch(() => {});
  };
  useEffect(load, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      const res = await fetch("/api/v1/academic/assignments", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth() },
        body: JSON.stringify({ ...form, course_id: Number(form.course_id) }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Failed - admin only");
      setForm({ course_id: "", title: "", description: "", max_score: 100 });
      load();
      setMsg("✅ Assignment created (stored in PostgreSQL/SQLite)");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  };

  const submit = async (id: number) => {
    const content = submitContent[id] || "";
    if (!content) return setMsg("❌ Enter submission text");
    try {
      const res = await fetch(`/api/v1/academic/assignments/${id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth() },
        body: JSON.stringify({ content, file_url: "" }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Submit failed");
      setMsg("✅ Submitted");
      load();
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📝 Assignments & Grades</h2>
      <p className="text-gray-600 mb-6">Stored in PostgreSQL (prod) or SQLite (laptop). Submissions can attach MinIO S3 file via <code>file_url</code>.</p>
      {msg && <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith("✅") ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>{msg}</div>}

      <form onSubmit={create} className="bg-white rounded-xl border shadow p-6 mb-6 space-y-4">
        <h3 className="font-semibold">Create Assignment (Admin)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <select value={form.course_id} onChange={(e) => setForm({ ...form, course_id: e.target.value })} className="rounded border px-3 py-2 text-sm" required>
            <option value="">Select course</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.code} - {c.title}</option>)}
          </select>
          <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Title" className="rounded border px-3 py-2 text-sm" required />
          <input type="number" value={form.max_score} onChange={(e) => setForm({ ...form, max_score: Number(e.target.value) })} className="rounded border px-3 py-2 text-sm" />
        </div>
        <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
        <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg text-sm">Create</button>
      </form>

      {loading ? <p className="text-gray-500">Loading...</p> : assignments.length === 0 ? <p className="text-center py-12 bg-white rounded-xl border">No assignments yet</p> : (
        <div className="space-y-4">
          {assignments.map((a) => (
            <div key={a.id} className="bg-white rounded-xl border shadow p-6">
              <h3 className="font-semibold">{a.title} <span className="text-xs bg-gray-100 px-2 py-1 rounded ml-2">Course {a.course_id} • Max {a.max_score}</span></h3>
              {a.description && <p className="text-sm text-gray-600 mt-1">{a.description}</p>}
              <div className="mt-4 flex gap-2">
                <input type="text" value={submitContent[a.id] || ""} onChange={(e) => setSubmitContent({ ...submitContent, [a.id]: e.target.value })} placeholder="Submission text or MinIO S3 key" className="flex-1 rounded border px-3 py-2 text-sm" />
                <button onClick={() => submit(a.id)} className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700">Submit</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
