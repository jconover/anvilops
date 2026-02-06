'use client';

import { useAuth } from '@/lib/auth/context';
import type { UserRole } from '@/lib/auth/roles';
import type { Permission } from '@/lib/auth/roles';

interface RoleGateProps {
  children: React.ReactNode;
  permission?: Permission;
  minimumRole?: UserRole;
  fallback?: React.ReactNode;
}

export function RoleGate({ children, permission, minimumRole, fallback = null }: RoleGateProps) {
  const { hasPermission, hasMinimumRole } = useAuth();

  if (permission && !hasPermission(permission)) return <>{fallback}</>;
  if (minimumRole && !hasMinimumRole(minimumRole)) return <>{fallback}</>;

  return <>{children}</>;
}
