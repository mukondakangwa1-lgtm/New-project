import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Layout from "@/components/Layout";

interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
}

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [enrollments, setEnrollments] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    const h = { Authorization: `Bearer ${token}` };
    fetch("/api/v1/users/me", { headers: h })
      .then((r) => {
        if (!r.ok) throw new Error("Not authenticated");
        return r.json();
      })
      .then((u) => {
        setUser(u);
        // fetch enrollments via courses (filter by user if endpoint supports, fallback to all)
        fetch("/api/v1/courses/", { headers: h }).then((r) => r.json()).then(() => {});
        // For now, try to get overview if admin, else show enrolled courses via local cache
      })
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/login");
      });

    fetch("/api/v1/health/db", { headers: h }).then((r) => r.json()).then(setHealth).catch(() => {});
    fetch("/api/v1/admin/analytics/overview", { headers: h }).then((r) => r.json()).then(setStats).catch(() => {});
  }, [router]);

  if (!user) {
    return (
      <Layout>
        <p className="text-gray-500">Loading dashboard...</p>
      </Layout>
    );
  }

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">Dashboard</h2>
      <p className="text-gray-600 mb-6">Welcome back, {user.full_name}! <span className="text-xs bg-gray-100 px-2 py-1 rounded">{user.is_admin ? "Admin" : "Student"}</span></p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="rounded-lg bg-white p-4 shadow border">
          <h3 className="font-semibold text-sm mb-1">👤 Profile</h3>
          <p className="text-sm text-gray-600 truncate">{user.email}</p>
          <p className="text-xs text-gray-400">ID: {user.id} • {user.is_active ? "Active" : "Inactive"}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow border">
          <h3 className="font-semibold text-sm mb-1">🗄️ Database</h3>
          <p className="text-sm font-mono">{health?.type || "Checking..."}</p>
          <p className="text-xs text-gray-400">{health?.tables ?? "?"} tables • {health?.latency_ms ?? "?"} ms</p>
          {health?.pgvector && <p className="text-xs text-green-600">pgvector ✅</p>}
        </div>
        <div className="rounded-lg bg-white p-4 shadow border">
          <h3 className="font-semibold text-sm mb-1">📚 Platform</h3>
          <p className="text-sm">{stats ? `${stats.courses?.total ?? 0} courses • ${stats.users?.total ?? 0} users` : "Login as admin to see stats"}</p>
          <p className="text-xs text-gray-400">{stats ? `${stats.courses?.enrollments ?? 0} enrollments` : ""}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow border">
          <h3 className="font-semibold text-sm mb-1">📦 Storage</h3>
          <p className="text-sm">MinIO/S3: <a href="/api/v1/storage/health" className="underline text-primary">health</a></p>
          <p className="text-xs text-gray-400">PostgreSQL + SQLite + S3</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <a href="/courses" className="rounded-lg bg-white p-6 shadow border hover:shadow-lg transition block">
          <h3 className="font-semibold text-lg mb-2">📚 Courses & Enroll</h3>
          <p className="text-sm text-gray-500">Browse and enroll — PostgreSQL/SQLite</p>
        </a>
        <a href="/assignments" className="rounded-lg bg-white p-6 shadow border hover:shadow-lg transition block">
          <h3 className="font-semibold text-lg mb-2">📝 Assignments</h3>
          <p className="text-sm text-gray-500">Submissions → MinIO S3</p>
        </a>
        <a href="/planner" className="rounded-lg bg-white p-6 shadow border hover:shadow-lg transition block">
          <h3 className="font-semibold text-lg mb-2">📅 Planner</h3>
          <p className="text-sm text-gray-500">Events & goals</p>
        </a>
      </div>

      <div className="flex gap-3">
        <a href="/hub/feed" className="text-sm bg-primary text-white px-4 py-2 rounded hover:bg-blue-800">Hub Feed</a>
        <a href="/kudos" className="text-sm bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">KUDOS Chat</a>
        <button onClick={() => { localStorage.removeItem("token"); router.push("/"); }} className="text-sm text-red-600 underline hover:text-red-800 px-4 py-2">Sign out</button>
      </div>
    </Layout>
  );
}
