'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { UserRole } from './roles';
import { hasPermission, hasMinimumRole, canAccessEnvironment, type Permission } from './roles';
import { signIn, signOut, getCurrentSession, getUserFromSession } from './cognito';

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
    async function checkSession() {
      try {
        const session = await getCurrentSession();
        if (session) {
          const cognitoUser = getUserFromSession(session);
          const idToken = session.getIdToken().getJwtToken();
          await fetch('/api/auth/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: idToken }),
          });
          setUser(cognitoUser);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }
    checkSession();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const session = await signIn(email, password);
      const cognitoUser = getUserFromSession(session);
      const idToken = session.getIdToken().getJwtToken();

      const res = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: idToken }),
      });
      if (!res.ok) {
        throw new Error('Failed to establish session');
      }

      setUser(cognitoUser);
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Login failed: ${error.message}`);
      }
      throw new Error('Login failed: An unexpected error occurred');
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await signOut();
    } finally {
      await fetch('/api/auth/session', { method: 'DELETE' }).catch(() => {});
      setUser(null);
    }
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
