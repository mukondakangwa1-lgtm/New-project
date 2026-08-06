import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Course {
  id: number;
  title: string;
  code: string;
  description: string;
  instructor: string;
  credits: number;
}

export default function Courses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/courses/")
      .then((r) => r.json())
      .then((data) => {
        setCourses(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <Layout>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold">📚 Courses</h2>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading courses...</p>
      ) : courses.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border shadow">
          <p className="text-5xl mb-4">📭</p>
          <p className="text-xl text-gray-600 mb-2">No courses yet</p>
          <p className="text-gray-500">
            Courses will appear here once an admin adds them via the API.
          </p>
          <p className="text-sm text-gray-400 mt-4">
            Try: <code className="bg-gray-100 px-2 py-1 rounded">POST /api/v1/courses/</code>
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course) => (
            <div
              key={course.id}
              className="rounded-xl bg-white p-6 shadow border hover:shadow-lg transition"
            >
              <div className="flex justify-between items-start mb-3">
                <span className="text-xs font-mono bg-primary text-white px-2 py-1 rounded">
                  {course.code}
                </span>
                <span className="text-xs text-gray-500">{course.credits} credits</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">{course.title}</h3>
              {course.description && (
                <p className="text-sm text-gray-600 mb-3">{course.description}</p>
              )}
              {course.instructor && (
                <p className="text-sm text-gray-500">
                  👤 {course.instructor}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
