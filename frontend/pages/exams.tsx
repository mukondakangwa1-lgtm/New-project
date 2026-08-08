import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

function auth(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function Exams() {
  const [exams, setExams] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ course_id: "", title: "", description: "", duration_minutes: 60 });
  const [qForm, setQForm] = useState<Record<number, any>>({});

  const load = () => {
    fetch("/api/v1/exams/", { headers: auth() })
      .then((r) => r.json())
      .then((d) => setExams(Array.isArray(d) ? d : []))
      .catch(() => setExams([]));
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
      const res = await fetch("/api/v1/exams/", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth() },
        body: JSON.stringify({ ...form, course_id: Number(form.course_id) }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Failed - admin only");
      setForm({ course_id: "", title: "", description: "", duration_minutes: 60 });
      load();
      setMsg("✅ Exam created (PostgreSQL/SQLite)");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  };

  const addQuestion = async (examId: number) => {
    const f = qForm[examId] || { question_text: "", question_type: "multiple_choice", options: '["A","B","C","D"]', correct_answer: "A" };
    if (!f.question_text) return setMsg("❌ Question text required");
    try {
      const res = await fetch(`/api/v1/exams/${examId}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth() },
        body: JSON.stringify({ question_text: f.question_text, question_type: f.question_type, options: f.options, correct_answer: f.correct_answer }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Add failed");
      setMsg("✅ Question added");
      setQForm({ ...qForm, [examId]: { question_text: "", question_type: "multiple_choice", options: '["A","B","C","D"]', correct_answer: "A" } });
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">🎓 Exams & Quizzes</h2>
      <p className="text-gray-600 mb-6">Auto-graded exams. Stored in PostgreSQL/SQLite.</p>
      {msg && <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith("✅") ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>{msg}</div>}

      <form onSubmit={create} className="bg-white rounded-xl border shadow p-6 mb-6 space-y-4">
        <h3 className="font-semibold">Create Exam (Admin)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <select value={form.course_id} onChange={(e) => setForm({ ...form, course_id: e.target.value })} className="rounded border px-3 py-2 text-sm" required>
            <option value="">Select course</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.code} - {c.title}</option>)}
          </select>
          <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Title e.g. Midterm" className="rounded border px-3 py-2 text-sm" required />
          <input type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} className="rounded border px-3 py-2 text-sm" />
        </div>
        <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
        <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg text-sm">Create Exam</button>
      </form>

      <div className="space-y-4">
        {exams.length === 0 ? <p className="text-center py-12 bg-white rounded-xl border">No exams yet</p> : exams.map((ex) => (
          <div key={ex.id} className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold">{ex.title} <span className="text-xs bg-gray-100 px-2 py-1 rounded">Course {ex.course_id} • {ex.duration_minutes} min</span></h3>
            {ex.description && <p className="text-sm text-gray-600 mt-1">{ex.description}</p>}
            <div className="mt-4 p-4 bg-gray-50 rounded border space-y-2">
              <p className="text-sm font-medium">Add Question</p>
              <input type="text" value={(qForm[ex.id]?.question_text)||""} onChange={(e)=> setQForm({...qForm, [ex.id]: {...(qForm[ex.id]||{}), question_text: e.target.value}})} placeholder="Question text" className="w-full rounded border px-3 py-2 text-sm" />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <select value={(qForm[ex.id]?.question_type)||"multiple_choice"} onChange={(e)=> setQForm({...qForm, [ex.id]: {...(qForm[ex.id]||{}), question_type: e.target.value}})} className="rounded border px-3 py-2 text-sm">
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="true_false">True/False</option>
                  <option value="short_answer">Short Answer</option>
                </select>
                <input type="text" value={(qForm[ex.id]?.options)||'["A","B","C","D"]'} onChange={(e)=> setQForm({...qForm, [ex.id]: {...(qForm[ex.id]||{}), options: e.target.value}})} placeholder='Options JSON' className="rounded border px-3 py-2 text-sm" />
                <input type="text" value={(qForm[ex.id]?.correct_answer)||"A"} onChange={(e)=> setQForm({...qForm, [ex.id]: {...(qForm[ex.id]||{}), correct_answer: e.target.value}})} placeholder="Correct answer" className="rounded border px-3 py-2 text-sm" />
              </div>
              <button onClick={()=> addQuestion(ex.id)} className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700">Add</button>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
}
