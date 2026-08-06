import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Layout from "@/components/Layout";

interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
}

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    fetch("/api/v1/users/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("Not authenticated");
        return r.json();
      })
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/login");
      });
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
      <p className="text-gray-600 mb-8">Welcome back, {user.full_name}!</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="rounded-lg bg-white p-6 shadow border">
          <h3 className="font-semibold text-lg mb-2">👤 Profile</h3>
          <p className="text-sm text-gray-600">{user.email}</p>
          <p className="text-xs text-gray-400 mt-1">ID: {user.id}</p>
        </div>
        <div className="rounded-lg bg-white p-6 shadow border">
          <h3 className="font-semibold text-lg mb-2">📚 My Courses</h3>
          <p className="text-gray-500 text-sm">No enrollments yet</p>
        </div>
        <div className="rounded-lg bg-white p-6 shadow border">
          <h3 className="font-semibold text-lg mb-2">📊 Status</h3>
          <p className="text-green-600 text-sm font-medium">
            {user.is_active ? "Active" : "Inactive"}
          </p>
        </div>
      </div>

      <button
        onClick={() => {
          localStorage.removeItem("token");
          router.push("/");
        }}
        className="text-sm text-red-600 underline hover:text-red-800"
      >
        Sign out
      </button>
    </Layout>
  );
}
