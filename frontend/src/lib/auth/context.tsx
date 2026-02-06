'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { UserRole } from './roles';
import { hasPermission, hasMinimumRole, canAccessEnvironment, type Permission } from './roles';

interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (permission: Permission) => boolean;
  hasMinimumRole: (role: UserRole) => boolean;
  canAccessEnvironment: (environment: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for existing session on mount
    const stored = localStorage.getItem('anvilops_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem('anvilops_user');
        localStorage.removeItem('anvilops_token');
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    // TODO: Replace with real Cognito auth when configured
    // For now, simulate auth for development
    const mockUser: User = {
      id: '1',
      email,
      name: email.split('@')[0],
      role: 'admin', // Default to admin for dev
    };
    localStorage.setItem('anvilops_user', JSON.stringify(mockUser));
    localStorage.setItem('anvilops_token', 'dev-token');
    setUser(mockUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('anvilops_user');
    localStorage.removeItem('anvilops_token');
    setUser(null);
  }, []);

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    hasPermission: (permission) => user ? hasPermission(user.role, permission) : false,
    hasMinimumRole: (role) => user ? hasMinimumRole(user.role, role) : false,
    canAccessEnvironment: (env) => user ? canAccessEnvironment(user.role, env) : false,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
