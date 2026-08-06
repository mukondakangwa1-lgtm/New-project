import { useState, FormEvent } from "react";
import { useRouter } from "next/router";
import Layout from "@/components/Layout";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Try proxy first, then direct
    const urls = ["/api/v1/auth/login", "http://127.0.0.1:8000/api/v1/auth/login"];

    for (const url of urls) {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (res.ok) {
          const data = await res.json();
          localStorage.setItem("token", data.access_token);
          router.push("/dashboard");
          setLoading(false);
          return;
        } else {
          const data = await res.json();
          throw new Error(data.detail || "Login failed");
        }
      } catch (err: any) {
        if (err.message === "Failed to fetch" && url === urls[0]) continue;
        setError(err.message);
        break;
      }
    }
    setLoading(false);
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-16">
        <div className="rounded-xl bg-white p-8 shadow-lg border">
          <h2 className="text-2xl font-bold mb-6 text-center">Sign In</h2>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="admin@campus.edu"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-white py-2 rounded font-medium hover:bg-blue-800 transition disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <div className="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-500">
            <p className="font-medium mb-1">Demo accounts:</p>
            <p>Admin: admin@campus.edu / admin123</p>
            <p>Student: student@campus.edu / student123</p>
          </div>

          <p className="text-center text-sm text-gray-500 mt-4">
            Don&apos;t have an account?{" "}
            <a href="/register" className="text-primary underline">Register</a>
          </p>
        </div>
      </div>
    </Layout>
  );
}
