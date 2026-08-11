import { useEffect } from "react";
import { useRouter } from "next/router";
import { useRole } from "@/lib/roles";

/**
 * Redirects guests / non-admins away from admin-only pages. Renders nothing
 * while the session is resolving, then either redirects or calls onReady.
 */
export function useAdminGuard(): boolean {
  const router = useRouter();
  const { role, loading } = useRole();
  const allowed = !loading && role === "admin";

  useEffect(() => {
    if (loading) return;
    if (role !== "admin") router.replace("/kudos");
  }, [loading, role, router]);

  return allowed;
}
