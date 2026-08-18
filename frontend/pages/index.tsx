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
  const [courseCount, setCourseCount] = useState<number>(0);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => r.json())
      .then((d) => setHealth(d.status))
      .catch(() => setHealth("offline"));

    fetch("/api/v1/courses/")
      .then((r) => r.json())
      .then((d) => setCourseCount(d.length))
      .catch(() => {});
  }, []);

  return (
    <Layout>
      <div className="text-center py-12">
        <h1 className="text-5xl font-bold text-primary mb-4">🎓 Digital Campus</h1>
        <p className="text-xl text-gray-600 mb-12">
          Unified Application — Manage courses, students, and enrollments.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="rounded-xl bg-white p-8 shadow-lg border hover:shadow-xl transition">
            <div className="text-4xl mb-4">🟢</div>
            <h2 className="text-xl font-semibold mb-2">Backend</h2>
            <p className={`font-mono text-lg ${health === "healthy" ? "text-green-600" : "text-red-600"}`}>
              {health}
            </p>
          </div>

          <div className="rounded-xl bg-white p-8 shadow-lg border hover:shadow-xl transition">
            <div className="text-4xl mb-4">📚</div>
            <h2 className="text-xl font-semibold mb-2">Courses</h2>
            <p className="font-mono text-3xl text-primary">{courseCount}</p>
            <p className="text-sm text-gray-500 mt-1">available</p>
          </div>

          <a href="/courses" className="rounded-xl bg-white p-8 shadow-lg border hover:shadow-xl transition block">
            <div className="text-4xl mb-4">→</div>
            <h2 className="text-xl font-semibold mb-2">Browse Courses</h2>
            <p className="text-gray-500">View and enroll in courses</p>
          </a>
        </div>

        <a
          href="/kudos"
          className="mt-10 inline-block rounded-xl bg-purple-50 border border-purple-200 px-8 py-5 hover:bg-purple-100 transition"
        >
          <p className="text-lg font-semibold text-purple-800">Ask KUDOS anything — no login needed</p>
          <p className="text-sm text-purple-700 mt-1">
            The campus guide answers your questions. After two messages, guests are invited to register for the full experience.
          </p>
        </a>
      </div>
    </Layout>
  );
}
