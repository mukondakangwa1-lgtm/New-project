import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

function auth(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function Planner() {
  const [events, setEvents] = useState<any[]>([]);
  const [goals, setGoals] = useState<any[]>([]);
  const [notifs, setNotifs] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [eForm, setEForm] = useState({ title: "", description: "", event_type: "custom", start_time: "", end_time: "", location: "" });
  const [gForm, setGForm] = useState({ title: "", description: "", goal_type: "daily", target_value: 1 });

  const load = () => {
    fetch("/api/v1/planner/calendar", { headers: auth() }).then((r)=>r.json()).then((d)=> setEvents(Array.isArray(d)?d:[])).catch(()=>{});
    fetch("/api/v1/planner/goals", { headers: auth() }).then((r)=>r.json()).then((d)=> setGoals(Array.isArray(d)?d:[])).catch(()=>{});
    fetch("/api/v1/planner/notifications", { headers: auth() }).then((r)=>r.json()).then((d)=> setNotifs(Array.isArray(d)?d:[])).catch(()=>{});
  };
  useEffect(load, []);

  const createEvent = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    if(!eForm.start_time || !eForm.end_time) return setMsg("❌ Start/end required");
    try{
      const res = await fetch("/api/v1/planner/calendar", {
        method:"POST", headers:{"Content-Type":"application/json", ...auth()},
        body: JSON.stringify(eForm)
      });
      if(!res.ok) throw new Error((await res.json()).detail||"Failed");
      setEForm({ title:"", description:"", event_type:"custom", start_time:"", end_time:"", location:"" });
      load(); setMsg("✅ Event created");
    }catch(e:any){ setMsg(`❌ ${e.message}`)}
  };

  const createGoal = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try{
      const res = await fetch("/api/v1/planner/goals", {
        method:"POST", headers:{"Content-Type":"application/json", ...auth()},
        body: JSON.stringify(gForm)
      });
      if(!res.ok) throw new Error((await res.json()).detail||"Failed");
      setGForm({ title:"", description:"", goal_type:"daily", target_value:1 });
      load(); setMsg("✅ Goal created");
    }catch(e:any){ setMsg(`❌ ${e.message}`)}
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📅 Calendar & Goals</h2>
      <p className="text-gray-600 mb-6">Personal planner stored in PostgreSQL/SQLite. Requires login.</p>
      {msg && <div className={`mb-4 p-3 rounded text-sm ${msg.startsWith("✅")?"bg-green-50 text-green-700 border border-green-200":"bg-red-50 text-red-700 border border-red-200"}`}>{msg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <form onSubmit={createEvent} className="bg-white rounded-xl border shadow p-6 space-y-3">
          <h3 className="font-semibold">Create Event</h3>
          <input type="text" value={eForm.title} onChange={(e)=> setEForm({...eForm, title:e.target.value})} placeholder="Title e.g. CS201 Lecture" className="w-full rounded border px-3 py-2 text-sm" required />
          <textarea value={eForm.description} onChange={(e)=> setEForm({...eForm, description:e.target.value})} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
          <div className="grid grid-cols-2 gap-3">
            <select value={eForm.event_type} onChange={(e)=> setEForm({...eForm, event_type:e.target.value})} className="rounded border px-3 py-2 text-sm">
              <option value="custom">Custom</option><option value="class">Class</option><option value="study">Study</option><option value="assignment">Assignment</option><option value="exam">Exam</option>
            </select>
            <input type="text" value={eForm.location} onChange={(e)=> setEForm({...eForm, location:e.target.value})} placeholder="Location" className="rounded border px-3 py-2 text-sm" />
          </div>
          <input type="datetime-local" value={eForm.start_time} onChange={(e)=> setEForm({...eForm, start_time:e.target.value})} className="w-full rounded border px-3 py-2 text-sm" required />
          <input type="datetime-local" value={eForm.end_time} onChange={(e)=> setEForm({...eForm, end_time:e.target.value})} className="w-full rounded border px-3 py-2 text-sm" required />
          <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg text-sm">Create Event</button>
        </form>

        <form onSubmit={createGoal} className="bg-white rounded-xl border shadow p-6 space-y-3">
          <h3 className="font-semibold">Create Study Goal</h3>
          <input type="text" value={gForm.title} onChange={(e)=> setGForm({...gForm, title:e.target.value})} placeholder="Goal e.g. Study 2h daily" className="w-full rounded border px-3 py-2 text-sm" required />
          <textarea value={gForm.description} onChange={(e)=> setGForm({...gForm, description:e.target.value})} placeholder="Description" className="w-full rounded border px-3 py-2 text-sm" rows={2} />
          <div className="grid grid-cols-2 gap-3">
            <select value={gForm.goal_type} onChange={(e)=> setGForm({...gForm, goal_type:e.target.value})} className="rounded border px-3 py-2 text-sm">
              <option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="custom">Custom</option>
            </select>
            <input type="number" value={gForm.target_value} onChange={(e)=> setGForm({...gForm, target_value:Number(e.target.value)})} className="rounded border px-3 py-2 text-sm" min={1} />
          </div>
          <button type="submit" className="bg-green-600 text-white px-6 py-2 rounded-lg text-sm">Create Goal</button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold mb-3">Events ({events.length})</h3>
          {events.length===0 ? <p className="text-sm text-gray-500">No events - create one</p> : events.slice(0,10).map((ev:any)=>(
            <div key={ev.id} className="border rounded p-2 mb-2">
              <p className="text-sm font-medium">{ev.title} <span className="text-xs bg-gray-100 px-1 rounded">{ev.event_type}</span></p>
              <p className="text-xs text-gray-500">{new Date(ev.start_time).toLocaleString()} → {new Date(ev.end_time).toLocaleString()}</p>
            </div>
          ))}
        </div>
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold mb-3">Goals ({goals.length})</h3>
          {goals.length===0 ? <p className="text-sm text-gray-500">No goals yet</p> : goals.map((g:any)=>(
            <div key={g.id} className="border rounded p-2 mb-2">
              <p className="text-sm font-medium">{g.title} <span className={`text-xs px-1 rounded ${g.is_completed?"bg-green-100 text-green-700":"bg-yellow-100"}`}>{g.is_completed?"Done":"Active"}</span></p>
              <p className="text-xs text-gray-500">{g.goal_type} • {g.current_value}/{g.target_value}</p>
            </div>
          ))}
        </div>
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold mb-3">Notifications ({notifs.length})</h3>
          {notifs.length===0 ? <p className="text-sm text-gray-500">No notifications</p> : notifs.slice(0,10).map((n:any)=>(
            <div key={n.id} className={`border rounded p-2 mb-2 ${n.is_read?"opacity-60":"bg-blue-50"}`}>
              <p className="text-sm font-medium">{n.title}</p>
              <p className="text-xs text-gray-600">{n.message?.slice(0,80)}</p>
              <p className="text-xs text-gray-400">{n.notification_type} • {n.is_read?"read":"unread"}</p>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
}
