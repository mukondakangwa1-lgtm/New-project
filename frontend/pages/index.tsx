import { useEffect } from "react";
import { useRouter } from "next/router";

/**
 * The platform now lands on KUDOS — everyone can chat right away,
 * logged in or not. Guests get the public chat; signed-in users get
 * their full assistant with personal history.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/kudos");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-400 text-sm">
      Opening KUDOS…
    </div>
  );
}