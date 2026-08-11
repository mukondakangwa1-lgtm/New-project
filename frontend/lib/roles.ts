import { useCallback, useEffect, useState } from "react";

export interface SessionUser {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  is_approved: boolean;
  is_student: boolean;
  school: string | null;
}

export type Role = "guest" | "user" | "student" | "admin";

export interface RoleState {
  role: Role;
  user: SessionUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function roleFor(user: SessionUser | null): Role {
  if (!user) return "guest";
  if (user.is_admin) return "admin";
  if (user.is_student) return "student";
  return "user";
}

export function useRole(): RoleState {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/users/me");
      if (res.status === 200) {
        setUser(await res.json());
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { role: roleFor(user), user, loading, refresh };
}
