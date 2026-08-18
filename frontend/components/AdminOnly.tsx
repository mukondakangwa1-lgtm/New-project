import { useEffect, useState } from "react";
import Layout from "@/components/Layout";

interface AdminOnlyProps {
  children: React.ReactNode;
  title?: string;
}

export default function AdminOnly({ children, title = "this section" }: AdminOnlyProps) {
  const [state, setState] = useState<"loading" | "denied" | "ok">("loading");

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setState("denied");
      return;
    }
    fetch("/api/v1/users/me", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then((user) => setState(user?.is_admin ? "ok" : "denied"))
      .catch(() => setState("denied"));
  }, []);

  if (state === "loading") {
    return (
      <Layout>
        <p className="text-gray-500">Checking access…</p>
      </Layout>
    );
  }

  if (state === "denied") {
    return (
      <Layout>
        <div className="text-center py-16">
          <p className="text-6xl mb-4">🔒</p>
          <h2 className="text-2xl font-bold mb-2">Superadmin only</h2>
          <p className="text-gray-600 mb-6">
            {title} is reserved for the superadmin. It is not part of the student campus.
          </p>
          <a
            href="/login"
            className="bg-primary text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-800 inline-block"
          >
            Login as Superadmin
          </a>
        </div>
      </Layout>
    );
  }

  return <>{children}</>;
}
