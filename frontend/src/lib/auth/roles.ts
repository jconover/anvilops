export type UserRole = 'viewer' | 'builder' | 'builder_prod' | 'approver' | 'admin';

export const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 0,
  builder: 1,
  builder_prod: 2,
  approver: 3,
  admin: 4,
};

export type Permission =
  | 'servers:view'
  | 'servers:create'
  | 'servers:create_prod'
  | 'servers:delete'
  | 'servers:approve'
  | 'compliance:view'
  | 'admin:access'
  | 'admin:manage_users';

export const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  viewer: ['servers:view', 'compliance:view'],
  builder: ['servers:view', 'servers:create', 'compliance:view'],
  builder_prod: ['servers:view', 'servers:create', 'servers:create_prod', 'compliance:view'],
  approver: ['servers:view', 'servers:create', 'servers:create_prod', 'servers:approve', 'compliance:view'],
  admin: [
    'servers:view', 'servers:create', 'servers:create_prod', 'servers:delete',
    'servers:approve', 'compliance:view', 'admin:access', 'admin:manage_users',
  ],
};

export function hasPermission(role: UserRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function hasMinimumRole(userRole: UserRole, requiredRole: UserRole): boolean {
  return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[requiredRole];
}

export function canAccessEnvironment(role: UserRole, environment: string): boolean {
  if (environment === 'production') {
    return hasMinimumRole(role, 'builder_prod');
  }
  return hasMinimumRole(role, 'builder');
}
