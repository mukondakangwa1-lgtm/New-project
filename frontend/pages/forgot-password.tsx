import { useState, FormEvent } from "react";
import Layout from "@/components/Layout";
import { useRouter } from "next/router";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch("/api/v1/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        throw new Error("Failed to send reset email");
      }

      setStatus("success");
      setMessage("If an account exists with that email, a password reset link has been sent.");
    } catch (err) {
      setStatus("error");
      setMessage("Unable to process request. Please try again later.");
    }
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-16">
        <div className="rounded-xl bg-white p-8 shadow-lg border">
          <h2 className="text-2xl font-bold mb-6 text-center">Reset Password</h2>
          
          {status === "success" ? (
            <div className="p-4 bg-green-50 text-green-700 rounded text-sm text-center">
              {message}
              <button 
                onClick={() => router.push("/login")}
                className="block w-full mt-4 bg-primary text-white py-2 rounded"
              >
                Back to Login
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {status === "error" && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded">{message}</div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={status === "loading"}
                className="w-full bg-primary text-white py-2 rounded font-medium"
              >
                {status === "loading" ? "Sending..." : "Send Reset Link"}
              </button>
            </form>
          )}
        </div>
      </div>
    </Layout>
  );
}
