import { useMemo, useState } from "react";

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          const ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="shrink-0 text-xs px-2 py-1 rounded border bg-white text-gray-500 hover:bg-gray-100 transition"
      title="Copy to clipboard"
    >
      {copied ? "✓ Copied" : label || "⧉ Copy"}
    </button>
  );
}

interface Segment {
  type: "text" | "code";
  content: string;
}

/**
 * Renders KUDOS message text with copy-paste friendly controls: every code
 * block and every full message gets a Copy button so codes/URLs/identifiers
 * can be copied exactly ("copy and paste mode").
 */
export default function MessageContent({ text }: { text: string }) {
  const segments = useMemo<Segment[]>(() => {
    const parts: Segment[] = [];
    const re = /```(\w*)\n?([\s\S]*?)```/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) parts.push({ type: "text", content: text.slice(last, m.index) });
      parts.push({ type: "code", content: m[2].replace(/\n$/, "") });
      last = m.index + m[0].length;
    }
    if (last < text.length) parts.push({ type: "text", content: text.slice(last) });
    if (parts.length === 0) parts.push({ type: "text", content: text });
    return parts;
  }, [text]);

  return (
    <div className="text-sm whitespace-pre-wrap space-y-2">
      {segments.map((seg, i) =>
        seg.type === "code" ? (
          <div key={i} className="bg-gray-900 rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800">
              <span className="text-[10px] uppercase tracking-wide text-gray-400">code</span>
              <CopyButton text={seg.content} label="Copy code" />
            </div>
            <pre className="p-3 text-xs text-gray-100 overflow-x-auto whitespace-pre-wrap break-all">
              {seg.content}
            </pre>
          </div>
        ) : (
          <span key={i} className="whitespace-pre-wrap">
            {seg.content}
          </span>
        )
      )}
    </div>
  );
}

export { CopyButton };
