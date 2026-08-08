import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Course {
  id: number;
  title: string;
  code: string;
  description: string;
  instructor: string;
  credits: number;
}

export default function Home() {
  const [health, setHealth] = useState<string>("checking...");
  const [dbHealth, setDbHealth] = useState<any>(null);
  const [storageHealth, setStorageHealth] = useState<any>(null);
  const [courseCount, setCourseCount] = useState<number>(0);

  useEffect(() => {
    fetch("/api/v1/health").then((r) => r.json()).then((d) => setHealth(d.status)).catch(() => setHealth("offline"));
    fetch("/api/v1/health/db").then((r) => r.json()).then(setDbHealth).catch(() => {});
    fetch("/api/v1/storage/health").then((r) => r.json()).then(setStorageHealth).catch(() => {});
    fetch("/api/v1/courses/").then((r) => r.json()).then((d) => setCourseCount(Array.isArray(d) ? d.length : 0)).catch(() => {});
  }, []);

  return (
    <Layout>
      <div className="text-center py-8 md:py-12">
        <h1 className="text-4xl md:text-5xl font-bold text-primary mb-3">🎓 Digital Campus</h1>
        <p className="text-lg text-gray-600 mb-2">PostgreSQL + SQLite + MinIO (S3) • Unified Campus Platform</p>
        <p className="text-sm text-gray-400 mb-8">Manage courses, enrollments, attendance, assignments, exams, chat, and KUDOS AI — all connected.</p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 max-w-5xl mx-auto mb-8">
          <div className="rounded-xl bg-white p-6 shadow border">
            <div className="text-2xl mb-2">🟢</div>
            <h2 className="font-semibold mb-1">Backend</h2>
            <p className={`font-mono text-sm ${health === "healthy" ? "text-green-600" : "text-red-600"}`}>{health}</p>
            <p className="text-xs text-gray-400 mt-1">{dbHealth?.type || ""} {dbHealth ? `• ${dbHealth.tables} tables` : ""}</p>
          </div>
          <div className="rounded-xl bg-white p-6 shadow border">
            <div className="text-2xl mb-2">🗄️</div>
            <h2 className="font-semibold mb-1">Database</h2>
            <p className="font-mono text-sm text-primary">{dbHealth?.type || "SQLite"}</p>
            <p className="text-xs text-gray-400">{storageHealth?.ok ? "S3 ✅" : "S3 offline"} • {dbHealth?.latency_ms ? `${dbHealth.latency_ms}ms` : ""}</p>
          </div>
          <div className="rounded-xl bg-white p-6 shadow border">
            <div className="text-2xl mb-2">📚</div>
            <h2 className="font-semibold mb-1">Courses</h2>
            <p className="font-mono text-2xl text-primary">{courseCount}</p>
            <p className="text-xs text-gray-500">available</p>
          </div>
          <div className="rounded-xl bg-white p-6 shadow border">
            <div className="text-2xl mb-2">📦</div>
            <h2 className="font-semibold mb-1">Storage</h2>
            <p className="font-mono text-sm">{storageHealth?.ok ? "MinIO ✅" : "MinIO ○"}</p>
            <p className="text-xs text-gray-400">PostgreSQL + SQLite + S3</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 max-w-5xl mx-auto">
          {[
            { href: "/courses", label: "📚 Courses", desc: "Enroll" },
            { href: "/assignments", label: "📝 Assignments", desc: "Submit to S3" },
            { href: "/exams", label: "🎓 Exams", desc: "Auto-graded" },
            { href: "/groups", label: "👥 Groups", desc: "Forums" },
            { href: "/planner", label: "📅 Planner", desc: "Events/Goals" },
            { href: "/register/attendance", label: "📋 Attendance", desc: "Check-in" },
            { href: "/hub/feed", label: "🌐 Hub", desc: "Share (S3)" },
            { href: "/chat", label: "💬 Chat", desc: "Real-time" },
            { href: "/kudos", label: "🧠 KUDOS", desc: "AI chat" },
            { href: "/kudos/upload", label: "📄 Upload", desc: "Teach AI" },
            { href: "/studio", label: "🎙️ Studio", desc: "Broadcast" },
            { href: "/admin/dashboard", label: "👑 Admin", desc: "Superadmin" },
          ].map((c) => (
            <a key={c.href} href={c.href} className="rounded-xl bg-white p-4 shadow border hover:shadow-lg transition block text-center">
              <div className="font-semibold text-sm">{c.label}</div>
              <div className="text-xs text-gray-500">{c.desc}</div>
            </a>
          ))}
        </div>

        <div className="mt-8 p-4 bg-white rounded-xl border max-w-5xl mx-auto text-left">
          <h3 className="font-semibold mb-2">🚀 Quick Start (3 storages connected)</h3>
          <code className="text-xs bg-gray-100 p-2 rounded block overflow-auto">
            # SQLite (laptop, zero setup) + MinIO<br />
            docker-compose up -d minio db redis<br />
            cd services/backend && python scripts/init_db.py --seed && python scripts/db_check.py<br />
            curl http://localhost:8000/api/v1/storage/health
          </code>
        </div>
      </div>
    </Layout>
  );
}
