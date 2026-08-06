import React from "react";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <a href="/" className="text-xl font-bold text-primary hover:text-blue-800 transition">
            🎓 Digital Campus
          </a>
          <ul className="flex gap-6 text-sm font-medium text-gray-600">
            <li><a href="/" className="hover:text-primary transition">Home</a></li>
            <li><a href="/courses" className="hover:text-primary transition">Courses</a></li>
            <li><a href="/register/attendance" className="hover:text-primary transition">Register</a></li>
            <li><a href="/studio" className="hover:text-primary transition">🎙️ Studio</a></li>
            <li><a href="/hub/feed" className="hover:text-primary transition">Hub</a></li>
            <li><a href="/chat" className="hover:text-primary transition">Chat</a></li>
            <li><a href="/kudos" className="hover:text-purple-600 transition font-bold text-purple-700">🧠 KUDOS</a></li>
            <li><a href="/kudos/connect" className="hover:text-purple-600 transition text-purple-600">🔌</a></li>
            <li><a href="/dashboard" className="hover:text-primary transition">Dashboard</a></li>
            <li><a href="/login" className="hover:text-primary transition">Login</a></li>
          </ul>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-8">{children}</main>
      <footer className="text-center text-xs text-gray-400 py-6">
        © 2026 Digital Campus
      </footer>
    </div>
  );
}
