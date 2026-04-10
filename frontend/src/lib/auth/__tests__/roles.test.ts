import { describe, it, expect } from 'vitest';
import {
  hasPermission,
  hasMinimumRole,
  canAccessEnvironment,
  ROLE_HIERARCHY,
  ROLE_PERMISSIONS,
  type UserRole,
  type Permission,
} from '../roles';

describe('ROLE_HIERARCHY', () => {
  it('assigns viewer the lowest level (0)', () => {
    expect(ROLE_HIERARCHY.viewer).toBe(0);
  });

  it('assigns admin the highest level (4)', () => {
    expect(ROLE_HIERARCHY.admin).toBe(4);
  });

  it('orders roles correctly: viewer < builder < builder_prod < approver < admin', () => {
    expect(ROLE_HIERARCHY.viewer).toBeLessThan(ROLE_HIERARCHY.builder);
    expect(ROLE_HIERARCHY.builder).toBeLessThan(ROLE_HIERARCHY.builder_prod);
    expect(ROLE_HIERARCHY.builder_prod).toBeLessThan(ROLE_HIERARCHY.approver);
    expect(ROLE_HIERARCHY.approver).toBeLessThan(ROLE_HIERARCHY.admin);
  });
});

describe('hasPermission()', () => {
  describe('viewer role', () => {
    it('can view servers', () => {
      expect(hasPermission('viewer', 'servers:view')).toBe(true);
    });

    it('can view compliance', () => {
      expect(hasPermission('viewer', 'compliance:view')).toBe(true);
    });

    it('cannot create servers', () => {
      expect(hasPermission('viewer', 'servers:create')).toBe(false);
    });

    it('cannot create prod servers', () => {
      expect(hasPermission('viewer', 'servers:create_prod')).toBe(false);
    });

    it('cannot delete servers', () => {
      expect(hasPermission('viewer', 'servers:delete')).toBe(false);
    });

    it('cannot approve servers', () => {
      expect(hasPermission('viewer', 'servers:approve')).toBe(false);
    });

    it('cannot access admin', () => {
      expect(hasPermission('viewer', 'admin:access')).toBe(false);
    });

    it('cannot manage users', () => {
      expect(hasPermission('viewer', 'admin:manage_users')).toBe(false);
    });
  });

  describe('builder role', () => {
    it('can view and create servers', () => {
      expect(hasPermission('builder', 'servers:view')).toBe(true);
      expect(hasPermission('builder', 'servers:create')).toBe(true);
    });

    it('cannot create prod servers', () => {
      expect(hasPermission('builder', 'servers:create_prod')).toBe(false);
    });

    it('cannot approve or delete servers', () => {
      expect(hasPermission('builder', 'servers:approve')).toBe(false);
      expect(hasPermission('builder', 'servers:delete')).toBe(false);
    });
  });

  describe('builder_prod role', () => {
    it('can create prod servers', () => {
      expect(hasPermission('builder_prod', 'servers:create_prod')).toBe(true);
    });

    it('cannot approve servers', () => {
      expect(hasPermission('builder_prod', 'servers:approve')).toBe(false);
    });

    it('cannot delete servers', () => {
      expect(hasPermission('builder_prod', 'servers:delete')).toBe(false);
    });
  });

  describe('approver role', () => {
    it('can approve servers', () => {
      expect(hasPermission('approver', 'servers:approve')).toBe(true);
    });

    it('cannot delete servers', () => {
      expect(hasPermission('approver', 'servers:delete')).toBe(false);
    });

    it('cannot access admin', () => {
      expect(hasPermission('approver', 'admin:access')).toBe(false);
    });
  });

  describe('admin role', () => {
    const allPermissions: Permission[] = [
      'servers:view',
      'servers:create',
      'servers:create_prod',
      'servers:delete',
      'servers:approve',
      'compliance:view',
      'admin:access',
      'admin:manage_users',
    ];

    it.each(allPermissions)('has permission: %s', (permission) => {
      expect(hasPermission('admin', permission)).toBe(true);
    });
  });
});

describe('hasMinimumRole()', () => {
  it('viewer meets viewer requirement', () => {
    expect(hasMinimumRole('viewer', 'viewer')).toBe(true);
  });

  it('viewer does not meet builder requirement', () => {
    expect(hasMinimumRole('viewer', 'builder')).toBe(false);
  });

  it('builder meets viewer requirement', () => {
    expect(hasMinimumRole('builder', 'viewer')).toBe(true);
  });

  it('builder meets builder requirement', () => {
    expect(hasMinimumRole('builder', 'builder')).toBe(true);
  });

  it('builder does not meet builder_prod requirement', () => {
    expect(hasMinimumRole('builder', 'builder_prod')).toBe(false);
  });

  it('admin meets all role requirements', () => {
    const roles: UserRole[] = ['viewer', 'builder', 'builder_prod', 'approver', 'admin'];
    for (const role of roles) {
      expect(hasMinimumRole('admin', role)).toBe(true);
    }
  });

  it('approver does not meet admin requirement', () => {
    expect(hasMinimumRole('approver', 'admin')).toBe(false);
  });
});

describe('canAccessEnvironment()', () => {
  describe('production environment', () => {
    it('viewer cannot access production', () => {
      expect(canAccessEnvironment('viewer', 'production')).toBe(false);
    });

    it('builder cannot access production', () => {
      expect(canAccessEnvironment('builder', 'production')).toBe(false);
    });

    it('builder_prod can access production', () => {
      expect(canAccessEnvironment('builder_prod', 'production')).toBe(true);
    });

    it('approver can access production', () => {
      expect(canAccessEnvironment('approver', 'production')).toBe(true);
    });

    it('admin can access production', () => {
      expect(canAccessEnvironment('admin', 'production')).toBe(true);
    });
  });

  describe('non-production environments (dev, staging)', () => {
    it('viewer cannot access dev', () => {
      expect(canAccessEnvironment('viewer', 'dev')).toBe(false);
    });

    it('builder can access dev', () => {
      expect(canAccessEnvironment('builder', 'dev')).toBe(true);
    });

    it('builder can access staging', () => {
      expect(canAccessEnvironment('builder', 'staging')).toBe(true);
    });

    it('admin can access dev', () => {
      expect(canAccessEnvironment('admin', 'dev')).toBe(true);
    });
  });
});
