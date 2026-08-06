import { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function RootDashboard() {
  const [identity, setIdentity] = useState<any>(null);
  const [guidelines, setGuidelines] = useState<string[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [terminalOutput, setTerminalOutput] = useState<string[]>(["Welcome to KUDOS Root Terminal", "Type 'help' for commands", ""]);
  const [terminalInput, setTerminalInput] = useState("");
  const [newName, setNewName] = useState("");
  const [newGuideline, setNewGuideline] = useState("");
  const [loading, setLoading] = useState(true);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    terminalRef.current?.scrollTo(0, terminalRef.current.scrollHeight);
  }, [terminalOutput]);

  const fetchData = async () => {
    try {
      const headers = getAuthHeader();
      const [idRes, guideRes, statusRes] = await Promise.all([
        fetch("/api/v1/root/identity", { headers }),
        fetch("/api/v1/root/guidelines", { headers }),
        fetch("/api/v1/root/status", { headers }),
      ]);
      if (idRes.ok) setIdentity(await idRes.json());
      if (guideRes.ok) {
        const d = await guideRes.json();
        setGuidelines(d.guidelines || []);
      }
      if (statusRes.ok) setStatus(await statusRes.json());
    } catch {}
    setLoading(false);
  };

  const executeCommand = async () => {
    if (!terminalInput.trim()) return;
    const cmd = terminalInput.trim();
    setTerminalOutput((prev) => [...prev, `$ ${cmd}`, ""]);
    setTerminalInput("");

    const parts = cmd.split(" ");
    const command = parts[0];
    const args = parts.slice(1).join(" ");

    const res = await fetch("/api/v1/root/root/exec", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ command, args }),
    });
    if (res.ok) {
      const data = await res.json();
      const output = typeof data.result === "string" ? data.result : JSON.stringify(data.result || data, null, 2);
      setTerminalOutput((prev) => [...prev, output, ""]);
    } else {
      setTerminalOutput((prev) => [...prev, `Error: ${res.statusText}`, ""]);
    }
  };

  const renameKudos = async () => {
    if (!newName) return;
    const res = await fetch(`/api/v1/root/identity/rename?new_name=${encodeURIComponent(newName)}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setTerminalOutput((prev) => [...prev, `Renamed: ${data.old_name} → ${data.new_name}`, ""]);
      setNewName("");
      fetchData();
    }
  };

  const addGuideline = async () => {
    if (!newGuideline) return;
    const res = await fetch(`/api/v1/root/guidelines/add?guideline=${encodeURIComponent(newGuideline)}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setNewGuideline("");
      fetchData();
    }
  };

  return (
    <Layout>
      <div className="mb-6">
        <h2 className="text-2xl md:text-3xl font-bold">👑 KUDOS Root</h2>
        <p className="text-gray-600 text-sm md:text-base">Superadmin control center — identity, guidelines, terminal, self-improvement</p>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading root access...</p>
      ) : (
        <div className="space-y-6">
          {/* Identity Card */}
          {identity && (
            <div className="bg-gradient-to-r from-purple-900 to-blue-900 rounded-xl p-4 md:p-6 text-white">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h3 className="text-2xl md:text-3xl font-bold">🤖 {identity.name}</h3>
                  <p className="text-purple-200 text-sm">{identity.full_name}</p>
                  <p className="text-purple-300 text-xs mt-1">"{identity.motto}"</p>
                  <p className="text-purple-400 text-xs mt-1">v{identity.version} • Created {identity.created_at}</p>
                </div>
                <div className="flex gap-2">
                  <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
                    className="bg-white/10 border border-white/20 rounded px-3 py-2 text-sm text-white placeholder-white/50"
                    placeholder="New name" />
                  <button onClick={renameKudos} className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded text-sm font-medium">
                    Rename
                  </button>
                </div>
              </div>

              {/* Body Parts */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                {identity.body && Object.entries(identity.body).map(([part, info]: [string, any]) => (
                  <div key={part} className="bg-white/10 rounded-lg p-3">
                    <p className="text-xs text-purple-300 uppercase">{part}</p>
                    <p className="font-semibold text-sm">{info.name}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <span className={`w-2 h-2 rounded-full ${info.status === "active" ? "bg-green-400" : "bg-red-400"}`} />
                      <span className="text-xs text-purple-200">{info.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Guidelines */}
          <div className="bg-white rounded-xl border shadow p-4 md:p-6">
            <h3 className="font-semibold text-lg mb-4">📜 KUDOS Guidelines</h3>
            <div className="space-y-2 mb-4">
              {guidelines.map((g, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-gray-400 font-mono">{i + 1}.</span>
                  <span>{g}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input type="text" value={newGuideline} onChange={(e) => setNewGuideline(e.target.value)}
                className="flex-1 rounded border px-3 py-2 text-sm"
                placeholder="Add new guideline..."
                onKeyDown={(e) => e.key === "Enter" && addGuideline()} />
              <button onClick={addGuideline} className="bg-primary text-white px-4 py-2 rounded text-sm hover:bg-blue-800">
                Add Rule
              </button>
            </div>
          </div>

          {/* Root Terminal */}
          <div className="bg-gray-900 rounded-xl overflow-hidden">
            <div className="bg-gray-800 px-4 py-2 flex justify-between items-center">
              <span className="text-green-400 font-mono text-sm">kudos@root:~$</span>
              <span className="text-gray-500 text-xs">Superadmin Terminal</span>
            </div>
            <div ref={terminalRef} className="p-4 h-64 overflow-y-auto font-mono text-sm text-green-400">
              {terminalOutput.map((line, i) => (
                <p key={i} className={line.startsWith("$") ? "text-yellow-400" : ""}>{line}</p>
              ))}
            </div>
            <div className="flex border-t border-gray-700">
              <span className="text-green-400 px-3 py-2 font-mono text-sm">$</span>
              <input type="text" value={terminalInput} onChange={(e) => setTerminalInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && executeCommand()}
                className="flex-1 bg-transparent text-green-400 font-mono text-sm px-2 py-2 outline-none"
                placeholder="Type a command (help, status, tree, files, read, gaps, abilities, log)" />
            </div>
          </div>

          {/* Self-Improvement */}
          {status && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border shadow p-4">
                <h3 className="font-semibold mb-3">🧠 Recent Improvements</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {(status.recent_improvements || []).map((imp: any, i: number) => (
                    <div key={i} className="text-xs border-b pb-1">
                      <span className="font-mono bg-gray-100 px-1 rounded">{imp.category}</span>
                      <span className="ml-2 text-gray-600">{imp.description}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white rounded-xl border shadow p-4">
                <h3 className="font-semibold mb-3">✨ New Abilities</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {(status.recent_abilities || []).length === 0 ? (
                    <p className="text-gray-500 text-sm">No new abilities yet — KUDOS is learning...</p>
                  ) : (
                    (status.recent_abilities || []).map((ab: any, i: number) => (
                      <div key={i} className="text-xs border-b pb-1">
                        <span className="font-semibold">{ab.ability}</span>
                        <span className="ml-2 text-gray-600">{ab.description}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
