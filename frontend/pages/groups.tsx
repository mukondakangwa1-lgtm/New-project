import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

function auth(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function Groups() {
  const [groups, setGroups] = useState<any[]>([]);
  const [threads, setThreads] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [gForm, setGForm] = useState({ name: "", description: "", course_id: "" });
  const [tForm, setTForm] = useState({ course_id: "", title: "", content: "" });

  const load = () => {
    fetch("/api/v1/groups/groups", { headers: auth() }).then((r)=>r.json()).then((d)=> setGroups(Array.isArray(d)?d:[])).catch(()=>{});
    fetch("/api/v1/groups/threads", { headers: auth() }).then((r)=>r.json()).then((d)=> setThreads(Array.isArray(d)?d:[])).catch(()=>{});
    fetch("/api/v1/courses/").then((r)=>r.json()).then((d)=> setCourses(Array.isArray(d)?d:[])).catch(()=>{});
  };
  useEffect(load, []);

  const createGroup = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      const res = await fetch("/api/v1/groups/groups", {
        method: "POST", headers: { "Content-Type":"application/json", ...auth() },
        body: JSON.stringify({ name: gForm.name, description: gForm.description, course_id: gForm.course_id? Number(gForm.course_id): null })
      });
      if(!res.ok) throw new Error((await res.json()).detail || "Failed");
      setGForm({ name:"", description:"", course_id:"" });
      load(); setMsg("✅ Group created");
    } catch(e:any){ setMsg(`❌ ${e.message}`)}
  };

  const createThread = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    if(!tForm.course_id) return setMsg("❌ Select course for thread");
    try{
      const res = await fetch("/api/v1/groups/threads", {
        method: "POST", headers: { "Content-Type":"application/json", ...auth() },
        body: JSON.stringify({ course_id: Number(tForm.course_id), title: tForm.title, content: tForm.content })
      });
      if(!res.ok) throw new Error((await res.json()).detail || "Failed");
      setTForm({ course_id:"", title:"", content:"" });
      load(); setMsg("✅ Thread created");
    }catch(e:any){ setMsg(`❌ ${e.message}`)}
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">👥 Study Groups & Forums</h2>
      <p className="text-gray-600 mb-6">Collaborate per course. PostgreSQL/SQLite.</p>
      {msg && <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith("✅")?"bg-green-50 text-green-700 border border-green-200":"bg-red-50 text-red-700 border border-red-200"}`}>{msg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <form onSubmit={createGroup} className="bg-white rounded-xl border shadow p-6 space-y-4">
          <h3 className="font-semibold">Create Study Group</h3>
          <input type="text" value={gForm.name} onChange={(e)=> setGForm({...gForm, name:e.target.value})} placeholder="Group name" className="w-full rounded border px-3 py-2 text-sm" required />
          <textarea value={gForm.description} onChange={(e)=> setGForm({...gForm, description:e.target.value})} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
          <select value={gForm.course_id} onChange={(e)=> setGForm({...gForm, course_id:e.target.value})} className="w-full rounded border px-3 py-2 text-sm">
            <option value="">No course (general)</option>
            {courses.map((c)=> <option key={c.id} value={c.id}>{c.code} - {c.title}</option>)}
          </select>
          <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg text-sm">Create Group</button>
        </form>

        <form onSubmit={createThread} className="bg-white rounded-xl border shadow p-6 space-y-4">
          <h3 className="font-semibold">Create Forum Thread</h3>
          <select value={tForm.course_id} onChange={(e)=> setTForm({...tForm, course_id:e.target.value})} className="w-full rounded border px-3 py-2 text-sm" required>
            <option value="">Select course</option>
            {courses.map((c)=> <option key={c.id} value={c.id}>{c.code} - {c.title}</option>)}
          </select>
          <input type="text" value={tForm.title} onChange={(e)=> setTForm({...tForm, title:e.target.value})} placeholder="Thread title" className="w-full rounded border px-3 py-2 text-sm" required />
          <textarea value={tForm.content} onChange={(e)=> setTForm({...tForm, content:e.target.value})} placeholder="Content" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
          <button type="submit" className="bg-green-600 text-white px-6 py-2 rounded-lg text-sm">Create Thread</button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold mb-3">Study Groups ({groups.length})</h3>
          {groups.length===0 ? <p className="text-sm text-gray-500">No groups yet</p> : groups.map((g:any)=>(
            <div key={g.id} className="border rounded p-3 mb-2">
              <p className="font-medium text-sm">{g.name}</p>
              {g.description && <p className="text-xs text-gray-600">{g.description}</p>}
              <p className="text-xs text-gray-400">Course: {g.course_id || "General"}</p>
            </div>
          ))}
        </div>
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold mb-3">Forum Threads ({threads.length})</h3>
          {threads.length===0 ? <p className="text-sm text-gray-500">No threads yet</p> : threads.map((t:any)=>(
            <div key={t.id} className="border rounded p-3 mb-2">
              <p className="font-medium text-sm">{t.title}</p>
              <p className="text-xs text-gray-600">{t.content?.slice(0,120)}</p>
              <p className="text-xs text-gray-400">Course {t.course_id} • {t.view_count ||0} views</p>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
}
