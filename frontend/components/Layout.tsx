import React, { useEffect, useState } from "react";
import { signOut } from "@/lib/api";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/v1/users/me")
      .then((r) => setSignedIn(r.status === 200))
      .catch(() => setSignedIn(false));
  }, []);

  const handleLogout = () => {
    if (!window.confirm("Logging out?")) return;
    signOut();
    window.location.assign("/kudos");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <a href="/" className="text-lg md:text-xl font-bold text-primary hover:text-blue-800 transition">
            🎓 Digital Campus
          </a>

          {/* Desktop nav */}
          <ul className="hidden md:flex gap-4 lg:gap-6 text-sm font-medium text-gray-600">
            <li><a href="/" className="hover:text-primary transition">Home</a></li>
            <li><a href="/courses" className="hover:text-primary transition">Courses</a></li>
            <li><a href="/register/attendance" className="hover:text-primary transition">Register</a></li>
            <li><a href="/media" className="hover:text-primary transition">🎬 Media</a></li>
            <li><a href="/studio" className="hover:text-primary transition">🎙️ Studio</a></li>
            <li><a href="/hub/feed" className="hover:text-primary transition">Hub</a></li>
            <li><a href="/chat" className="hover:text-primary transition">Chat</a></li>
            <li><a href="/kudos" className="hover:text-purple-600 transition font-bold text-purple-700">🧠 KUDOS</a></li>
            <li><a href="/admin/dashboard" className="hover:text-yellow-600 transition text-yellow-600">👑</a></li>
            <li><a href="/dashboard" className="hover:text-primary transition">Dashboard</a></li>
          </ul>

          {/* Session controls — top-right, always visible on desktop */}
          <div className="hidden md:flex items-center gap-2">
            {signedIn === false && (
              <a
                href="/login"
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-blue-800 transition"
              >
                Log in
              </a>
            )}
            {signedIn === true && (
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
              {[
                { href: "/", label: "🏠 Home" },
                { href: "/courses", label: "📚 Courses" },
                { href: "/register/attendance", label: "📋 Register" },
                { href: "/studio", label: "🎙️ Studio" },
                { href: "/media", label: "🎬 Media" },
                { href: "/hub/feed", label: "🌐 Hub" },
                { href: "/chat", label: "💬 Chat" },
                { href: "/kudos", label: "🧠 KUDOS" },
                { href: "/kudos/connect", label: "🔌 Connectors" },
                { href: "/kudos/autolearn", label: "🚀 Auto-Learn" },
                { href: "/kudos/maps", label: "🗺️ Maps" },
                { href: "/kudos/networks", label: "📡 Networks" },
                { href: "/admin/dashboard", label: "👑 Superadmin" },
                { href: "/dashboard", label: "📊 Dashboard" },
              ].map((item) => (
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
                {signedIn === true ? (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      handleLogout();
                    }}
                    className="w-full text-left py-2 px-3 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-red-600 transition"
                  >
                    🚪 Log out
                  </button>
                ) : (
                  <a
                    href="/login"
                    className="block py-2 px-3 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-primary transition"
                    onClick={() => setMenuOpen(false)}
                  >
                    🔑 Login
                  </a>
                )}
              </li>
            </ul>
          </div>
        )}
      </nav>

      <main className="max-w-7xl mx-auto px-3 md:px-4 py-4 md:py-8">{children}</main>

      <footer className="text-center text-xs text-gray-400 py-4 md:py-6 border-t">
        © 2026 Digital Campus • Powered by KUDOS AI
      </footer>
    </div>
  );
}
