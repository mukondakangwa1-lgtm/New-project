import React, { useState } from "react";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <a href="/" className="text-lg md:text-xl font-bold text-primary hover:text-blue-800 transition">
            🎓 Digital Campus
          </a>

          {/* Desktop nav */}
          <ul className="hidden md:flex gap-2 lg:gap-3 text-sm font-medium text-gray-600 flex-wrap items-center">
            <li><a href="/" className="hover:text-primary transition px-1">Home</a></li>
            <li><a href="/courses" className="hover:text-primary transition px-1">Courses</a></li>
            <li><a href="/assignments" className="hover:text-primary transition px-1">Assignments</a></li>
            <li><a href="/exams" className="hover:text-primary transition px-1">Exams</a></li>
            <li><a href="/groups" className="hover:text-primary transition px-1">Groups</a></li>
            <li><a href="/planner" className="hover:text-primary transition px-1">Planner</a></li>
            <li><a href="/register/attendance" className="hover:text-primary transition px-1">Register</a></li>
            <li><a href="/hub/feed" className="hover:text-primary transition px-1">Hub</a></li>
            <li><a href="/chat" className="hover:text-primary transition px-1">Chat</a></li>
            <li><a href="/media" className="hover:text-primary transition px-1">🎬 Media</a></li>
            <li><a href="/studio" className="hover:text-primary transition px-1">🎙️ Studio</a></li>
            <li><a href="/kudos" className="hover:text-purple-600 transition font-bold text-purple-700 px-1">🧠 KUDOS</a></li>
            <li><a href="/admin/dashboard" className="hover:text-yellow-600 transition text-yellow-600 px-1">👑</a></li>
            <li><a href="/dashboard" className="hover:text-primary transition px-1">Dashboard</a></li>
            <li><a href="/login" className="hover:text-primary transition px-1">Login</a></li>
          </ul>

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
                { href: "/assignments", label: "📝 Assignments" },
                { href: "/exams", label: "🎓 Exams" },
                { href: "/groups", label: "👥 Groups & Forums" },
                { href: "/planner", label: "📅 Planner" },
                { href: "/register/attendance", label: "📋 Register" },
                { href: "/hub/feed", label: "🌐 Hub" },
                { href: "/hub/new", label: "📤 Share (S3)" },
                { href: "/chat", label: "💬 Chat" },
                { href: "/media", label: "🎬 Media" },
                { href: "/studio", label: "🎙️ Studio" },
                { href: "/kudos", label: "🧠 KUDOS" },
                { href: "/kudos/connect", label: "🔌 Connectors" },
                { href: "/kudos/autolearn", label: "🚀 Auto-Learn" },
                { href: "/kudos/upload", label: "📄 Upload" },
                { href: "/admin/dashboard", label: "👑 Superadmin" },
                { href: "/dashboard", label: "📊 Dashboard" },
                { href: "/login", label: "🔑 Login" },
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
            </ul>
          </div>
        )}
      </nav>

      <main className="max-w-7xl mx-auto px-3 md:px-4 py-4 md:py-8">{children}</main>

      <footer className="text-center text-xs text-gray-400 py-4 md:py-6 border-t">
        © 2026 Digital Campus • PostgreSQL + SQLite + MinIO (S3) • Powered by KUDOS AI
      </footer>
    </div>
  );
}
