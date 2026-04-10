import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { RoleGate } from '../role-gate';
import type { Permission } from '@/lib/auth/roles';
import type { UserRole } from '@/lib/auth/roles';

// Mock useAuth — each test overrides returnValue as needed
const mockHasPermission = vi.fn();
const mockHasMinimumRole = vi.fn();

vi.mock('@/lib/auth/context', () => ({
  useAuth: () => ({
    user: { id: '1', email: 'test@example.com', name: 'Test User', role: 'builder' },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    hasPermission: mockHasPermission,
    hasMinimumRole: mockHasMinimumRole,
    canAccessEnvironment: vi.fn(),
  }),
}));

function setup(props: Parameters<typeof RoleGate>[0]) {
  return render(<RoleGate {...props} />);
}

describe('RoleGate', () => {
  describe('permission prop', () => {
    it('renders children when hasPermission returns true', () => {
      mockHasPermission.mockReturnValue(true);
      setup({ permission: 'servers:create', children: <span>Protected Content</span> });
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });

    it('hides children when hasPermission returns false', () => {
      mockHasPermission.mockReturnValue(false);
      setup({ permission: 'servers:create', children: <span>Protected Content</span> });
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('renders fallback when hasPermission returns false and fallback is provided', () => {
      mockHasPermission.mockReturnValue(false);
      setup({
        permission: 'admin:access',
        children: <span>Admin Area</span>,
        fallback: <span>Access Denied</span>,
      });
      expect(screen.queryByText('Admin Area')).not.toBeInTheDocument();
      expect(screen.getByText('Access Denied')).toBeInTheDocument();
    });

    it('renders nothing (null fallback) when permission denied and no fallback given', () => {
      mockHasPermission.mockReturnValue(false);
      const { container } = setup({
        permission: 'admin:manage_users',
        children: <span>Hidden</span>,
      });
      expect(container.firstChild).toBeNull();
    });

    it('calls hasPermission with the correct permission value', () => {
      mockHasPermission.mockReturnValue(true);
      setup({ permission: 'servers:delete', children: <span>Content</span> });
      expect(mockHasPermission).toHaveBeenCalledWith('servers:delete');
    });
  });

  describe('minimumRole prop', () => {
    it('renders children when hasMinimumRole returns true', () => {
      mockHasMinimumRole.mockReturnValue(true);
      setup({ minimumRole: 'builder', children: <span>Builder Content</span> });
      expect(screen.getByText('Builder Content')).toBeInTheDocument();
    });

    it('hides children when hasMinimumRole returns false', () => {
      mockHasMinimumRole.mockReturnValue(false);
      setup({ minimumRole: 'admin', children: <span>Admin Content</span> });
      expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
    });

    it('renders fallback when minimumRole check fails', () => {
      mockHasMinimumRole.mockReturnValue(false);
      setup({
        minimumRole: 'admin',
        children: <span>Admin Panel</span>,
        fallback: <span>Insufficient Role</span>,
      });
      expect(screen.getByText('Insufficient Role')).toBeInTheDocument();
    });

    it('calls hasMinimumRole with the correct role', () => {
      mockHasMinimumRole.mockReturnValue(true);
      setup({ minimumRole: 'approver', children: <span>Content</span> });
      expect(mockHasMinimumRole).toHaveBeenCalledWith('approver');
    });
  });

  describe('no gate props (passthrough)', () => {
    it('renders children when neither permission nor minimumRole is provided', () => {
      setup({ children: <span>Open Content</span> });
      expect(screen.getByText('Open Content')).toBeInTheDocument();
    });
  });

  describe('both permission and minimumRole provided', () => {
    it('checks permission first — blocks if permission fails even if role passes', () => {
      mockHasPermission.mockReturnValue(false);
      mockHasMinimumRole.mockReturnValue(true);
      setup({
        permission: 'servers:delete',
        minimumRole: 'builder',
        children: <span>Dual Gated</span>,
        fallback: <span>Blocked</span>,
      });
      expect(screen.queryByText('Dual Gated')).not.toBeInTheDocument();
      expect(screen.getByText('Blocked')).toBeInTheDocument();
    });

    it('renders children when both permission and minimumRole pass', () => {
      mockHasPermission.mockReturnValue(true);
      mockHasMinimumRole.mockReturnValue(true);
      setup({
        permission: 'servers:create',
        minimumRole: 'builder',
        children: <span>Dual Gated Content</span>,
      });
      expect(screen.getByText('Dual Gated Content')).toBeInTheDocument();
    });
  });
});
