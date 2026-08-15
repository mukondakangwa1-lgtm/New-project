import React from "react";
import Link from "next/link";
import ChatWidget from "./ChatWidget";
import { signOut } from "@/lib/api";
import { useRole, Role } from "@/lib/roles";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const { role, loading } = useRole();

  const handleLogout = () => {
    if (!window.confirm("Logging out?")) return;
    signOut();
    window.location.assign("/kudos");
  };

  const navItems: Array<{ href: string; label: string; roles: Role[] }> = [
    { href: "/kudos", label: "🧠 KUDOS", roles: ["guest", "user", "student", "admin"] },
    { href: "/studio", label: "🎙️ Studio", roles: ["user", "student", "admin"] },
    { href: "/media", label: "🎬 Media", roles: ["user", "student", "admin"] },
    { href: "/hub", label: "🌐 Hub", roles: ["user", "student", "admin"] },
    { href: "/kudos/maps", label: "🗺️ Maps", roles: ["user", "student", "admin"] },
    { href: "/library", label: "📚 Library", roles: ["user", "student", "admin"] },
    { href: "/dashboard", label: "📊 Dashboard", roles: ["user", "student", "admin"] },
    { href: "/courses", label: "🎓 Courses & Register", roles: ["student"] },
    { href: "/kudos/networks", label: "📡 Networks", roles: ["admin"] },
    { href: "/kudos/connect", label: "🔌 Connectors", roles: ["admin"] },
    { href: "/kudos/autolearn", label: "🚀 Auto-Learn", roles: ["admin"] },
    { href: "/kudos/agent", label: "🤖 Agent", roles: ["admin"] },
    { href: "/kudos/llm", label: "🧪 LLM", roles: ["admin"] },
    { href: "/kudos/learn", label: "🎓 Learn", roles: ["admin"] },
    { href: "/kudos/upload", label: "📤 Upload", roles: ["admin"] },
    { href: "/kudos/archive", label: "🗄️ Archive", roles: ["admin"] },
    { href: "/admin/dashboard", label: "👑 Superadmin", roles: ["admin"] },
  ];

  const visible = navItems.filter((item) => item.roles.includes(role));

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <Link href="/" className="text-lg md:text-xl font-bold text-primary hover:text-blue-800 transition">
            🎓 Digital Campus
          </Link>

          {/* Desktop nav */}
          <ul className="hidden md:flex gap-4 lg:gap-6 text-sm font-medium text-gray-600">
            {visible.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="hover:text-primary transition">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>

          {/* Session controls — top-right, always visible on desktop */}
          <div className="hidden md:flex items-center gap-2">
            {role === "guest" && (
              <Link
                href="/login"
                className="px-8 py-3 rounded-lg bg-primary text-white text-lg font-bold hover:bg-blue-800 transition shadow"
              >
                Sign in
              </Link>
            )}
            {role !== "guest" && (
              <button
                onClick={handleLogout}
                className="px-3 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:border-red-300 hover:text-red-600 transition"
              >
                Log out
              </button>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-100"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden bg-white border-t border-gray-100 px-4 py-3 shadow-lg">
            <ul className="space-y-2">
              {visible.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    className="block py-2 px-3 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-primary transition"
                    onClick={() => setMenuOpen(false)}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
              <li>
                {role === "guest" ? (
                  <Link
                    href="/login"
                    className="block py-2 px-3 rounded-lg text-sm font-bold text-gray-700 hover:bg-gray-100 hover:text-primary transition"
                    onClick={() => setMenuOpen(false)}
                  >
                    🔑 Sign in
                  </Link>
                ) : (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      handleLogout();
                    }}
                    className="w-full text-left py-2 px-3 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-red-600 transition"
                  >
                    🚪 Log out
                  </button>
                )}
              </li>
            </ul>
          </div>
        )}
      </nav>

      <main className="max-w-7xl mx-auto px-3 md:px-4 py-4 md:py-8">{loading ? null : children}</main>

      <ChatWidget />
      <footer className="text-center text-xs text-gray-400 py-4 md:py-6 border-t">
        © 2026 Digital Campus • Powered by KUDOS AI
      </footer>
    </div>
  );
}
