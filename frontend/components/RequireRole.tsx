import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { useRole, Role } from "@/lib/roles";

interface RequireRoleProps {
  roles?: Role[];
  children: React.ReactNode;
  redirectTo?: string;
}

export default function RequireRole({ roles, children, redirectTo = "/kudos" }: RequireRoleProps) {
  const { role, loading } = useRole();
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (roles && !roles.includes(role)) {
      router.replace(redirectTo);
      return;
    }
    setChecked(true);
  }, [loading, role, roles, router, redirectTo]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-400 text-sm">
        Loading…
      </div>
    );
  }

  if (!checked) return null;
  return <>{children}</>;
}
