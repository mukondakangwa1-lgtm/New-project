import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface IntegrityResult {
  status: string;
  violations: { file: string; expected: string; actual: string; status: string }[];
  message: string;
  saved_at: string;
}
interface SystemStatus {
  integrity: IntegrityResult;
  improvement: {
    total_questions: number;
    answer_rate: string;
    average_rating: number;
    recommendation: string;
  };
  protected_files: number;
  secure_channel: string;
}
interface ImprovementReport {
  total_questions: number;
  questions_answered: number;
  questions_unanswered: number;
  answer_rate: string;
  knowledge_gaps: { topic: string; count: number }[];
  popular_topics: { topic: string; count: number }[];
  feedback_count: number;
  average_rating: number;
  recommendation: string;
}
interface AuditEntry {
  user_id: number;
  action: string;
  details: string;
  timestamp: string;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosGuardian() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [improvement, setImprovement] = useState<ImprovementReport | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statusRes, improvRes, auditRes] = await Promise.all([
        fetch("/api/v1/kudos/guardian/system/status", { headers: getAuthHeader() }),
        fetch("/api/v1/kudos/guardian/improvement/report", { headers: getAuthHeader() }),
        fetch("/api/v1/kudos/guardian/channel/audit", { headers: getAuthHeader() }),
      ]);
      if (statusRes.ok) setStatus(await statusRes.json());
      if (improvRes.ok) setImprovement(await improvRes.json());
      if (auditRes.ok) {
        const data = await auditRes.json();
        setAuditLog(data.entries || []);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const openChannel = async () => {
    const res = await fetch("/api/v1/kudos/guardian/channel/open", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `🔒 ${data.message}`, type: "success" });
      fetchAll();
    }
  };

  const verifyIntegrity = async () => {
    const res = await fetch("/api/v1/kudos/guardian/integrity", { headers: getAuthHeader() });
    if (res.ok) {
      const data: IntegrityResult = await res.json();
      if (data.status === "INTEGR") {
        setMessage({ text: "✅ All KUDOS files are intact and verified", type: "success" });
      } else {
        setMessage({ text: `⚠️ ${data.message}`, type: "error" });
      }
    }
  };

  const updateHashes = async () => {
    const res = await fetch("/api/v1/kudos/guardian/integrity/update", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setMessage({ text: "✅ Integrity hashes updated", type: "success" });
      fetchAll();
    }
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold">🛡️ KUDOS Guardian</h2>
          <p className="text-gray-600">
            Security, integrity, and self-improvement controls — superadmin only
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={openChannel}
            className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700"
          >
            🔒 Open Secure Channel
          </button>
          <button
            onClick={verifyIntegrity}
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            🔍 Verify Integrity
          </button>
          <button
            onClick={updateHashes}
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            🔄 Update Hashes
          </button>
        </div>
      </div>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${
          message.type === "success" ? "bg-green-50 border border-green-200 text-green-700"
            : "bg-red-50 border border-red-200 text-red-700"
        }`}>{message.text}</div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading guardian status...</p>
      ) : (
        <div className="space-y-6">
          {/* System Status */}
          {status && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border shadow p-5 text-center">
                <p className="text-3xl mb-2">
                  {status.integrity?.status === "INTEGR" ? "🟢" : "🔴"}
                </p>
                <p className="font-semibold">File Integrity</p>
                <p className="text-sm text-gray-500">{status.integrity?.status}</p>
              </div>
              <div className="bg-white rounded-xl border shadow p-5 text-center">
                <p className="text-3xl mb-2">📄</p>
                <p className="font-semibold">Protected Files</p>
                <p className="text-2xl font-bold text-primary">{status.protected_files}</p>
              </div>
              <div className="bg-white rounded-xl border shadow p-5 text-center">
                <p className="text-3xl mb-2">🔒</p>
                <p className="font-semibold">Secure Channel</p>
                <p className="text-sm text-gray-500">{status.secure_channel}</p>
              </div>
              <div className="bg-white rounded-xl border shadow p-5 text-center">
                <p className="text-3xl mb-2">📊</p>
                <p className="font-semibold">Answer Rate</p>
                <p className="text-2xl font-bold text-green-600">{status.improvement?.answer_rate}</p>
              </div>
            </div>
          )}

          {/* Integrity Violations */}
          {status?.integrity?.violations && status.integrity.violations.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-5">
              <h3 className="font-semibold text-red-700 mb-3">⚠️ Integrity Violations Detected</h3>
              <div className="space-y-2">
                {status.integrity.violations.map((v, i) => (
                  <div key={i} className="bg-white rounded p-3 text-sm">
                    <p className="font-mono text-red-600">{v.file}</p>
                    <p className="text-gray-500">
                      Status: {v.status} | Expected: {v.expected} | Actual: {v.actual}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Self-Improvement Report */}
          {improvement && (
            <div className="bg-white rounded-xl border shadow p-6">
              <h3 className="font-semibold text-lg mb-4">🧠 Self-Improvement Report</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <p className="text-sm text-gray-500">Total Questions</p>
                  <p className="text-2xl font-bold">{improvement.total_questions}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Answer Rate</p>
                  <p className="text-2xl font-bold text-green-600">{improvement.answer_rate}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Avg Rating</p>
                  <p className="text-2xl font-bold">{improvement.average_rating}/5</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Feedback</p>
                  <p className="text-2xl font-bold">{improvement.feedback_count}</p>
                </div>
              </div>

              <div className="bg-blue-50 rounded-lg p-4 mb-4">
                <p className="text-sm font-medium text-blue-700">💡 Recommendation</p>
                <p className="text-sm text-blue-600">{improvement.recommendation}</p>
              </div>

              {improvement.knowledge_gaps.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Knowledge Gaps</p>
                  <div className="flex flex-wrap gap-2">
                    {improvement.knowledge_gaps.map((g, i) => (
                      <span key={i} className="bg-red-100 text-red-700 px-2 py-1 rounded text-xs">
                        {g.topic} ({g.count}x)
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {improvement.popular_topics.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">Popular Topics</p>
                  <div className="flex flex-wrap gap-2">
                    {improvement.popular_topics.map((t, i) => (
                      <span key={i} className="bg-green-100 text-green-700 px-2 py-1 rounded text-xs">
                        {t.topic} ({t.count}x)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Audit Log */}
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">📋 Audit Log</h3>
            {auditLog.length === 0 ? (
              <p className="text-gray-500 text-sm">No commands executed yet</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {auditLog.map((entry, i) => (
                  <div key={i} className="flex justify-between items-center text-sm border-b pb-2">
                    <div>
                      <span className="font-mono bg-gray-100 px-2 py-0.5 rounded mr-2">
                        {entry.action}
                      </span>
                      <span className="text-gray-500">{entry.details}</span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(entry.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
