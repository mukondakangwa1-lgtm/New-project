import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Post {
  id: number;
  title: string;
  description: string;
  storage_url: string;
  storage_type: string;
  content_type: string;
  thumbnail_url: string;
  is_public: boolean;
  tags: string;
  view_count: number;
  created_at: string;
  author: { id: number; full_name: string; email: string };
  reaction_count: number;
  comment_count: number;
}

const STORAGE_ICONS: Record<string, string> = {
  gdrive: "📁",
  dropbox: "📦",
  onedrive: "☁️",
  s3: "🪣",
  youtube: "▶️",
  image: "🖼️",
  video: "🎬",
  document: "📄",
  link: "🔗",
};

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function SocialFeed() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPosts();
  }, [filter]);

  const fetchPosts = async () => {
    setLoading(true);
    let url = "/api/v1/social/feed?limit=50";
    if (filter) url += `&storage_type=${filter}`;
    try {
      const res = await fetch(url);
      if (res.ok) setPosts(await res.json());
    } catch (e) {}
    setLoading(false);
  };

  const react = async (postId: number) => {
    await fetch(`/api/v1/social/${postId}/react`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ emoji: "👍" }),
    });
    fetchPosts();
  };

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-3xl font-bold">🌐 Social Hub</h2>
          <p className="text-gray-600">Browse shared resources from any storage</p>
        </div>
        <a
          href="/hub/new"
          className="bg-primary text-white px-5 py-2 rounded-lg font-medium hover:bg-blue-800 transition"
        >
          + Share Resource
        </a>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {["", "link", "gdrive", "dropbox", "youtube", "image", "video", "document"].map(
          (t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`px-3 py-1 rounded-full text-sm transition ${
                filter === t
                  ? "bg-primary text-white"
                  : "bg-white border text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t || "All"}
            </button>
          )
        )}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading feed...</p>
      ) : posts.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <p className="text-5xl mb-3">🌐</p>
          <p className="text-xl text-gray-600 mb-2">No posts yet</p>
          <p className="text-gray-500">Be the first to share a resource!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {posts.map((post) => (
            <div
              key={post.id}
              className="bg-white rounded-xl border shadow hover:shadow-lg transition overflow-hidden"
            >
              {/* Thumbnail or icon */}
              {post.thumbnail_url ? (
                <img
                  src={post.thumbnail_url}
                  alt={post.title}
                  className="w-full h-48 object-cover"
                />
              ) : (
                <div className="w-full h-32 bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center text-5xl">
                  {STORAGE_ICONS[post.storage_type] || "🔗"}
                </div>
              )}

              <div className="p-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                    {STORAGE_ICONS[post.storage_type]} {post.storage_type}
                  </span>
                  {post.content_type && (
                    <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                      {post.content_type}
                    </span>
                  )}
                </div>

                <h3 className="font-semibold text-lg mb-1 line-clamp-2">{post.title}</h3>
                {post.description && (
                  <p className="text-sm text-gray-500 mb-3 line-clamp-2">{post.description}</p>
                )}

                <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
                  <span>by {post.author?.full_name || "Unknown"}</span>
                  <span>{timeAgo(post.created_at)}</span>
                </div>

                {post.tags && (
                  <div className="flex gap-1 flex-wrap mb-3">
                    {post.tags.split(",").map((tag, i) => (
                      <span key={i} className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                        #{tag.trim()}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-4 pt-3 border-t">
                  <a
                    href={post.storage_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary text-sm font-medium hover:underline flex-1"
                  >
                    Open Resource →
                  </a>
                  <button
                    onClick={() => react(post.id)}
                    className="text-sm text-gray-500 hover:text-primary transition"
                  >
                    👍 {post.reaction_count || ""}
                  </button>
                  <span className="text-sm text-gray-400">
                    👁 {post.view_count}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
