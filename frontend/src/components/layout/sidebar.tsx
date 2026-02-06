'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Hammer,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  LogOut,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth/context';
import type { Permission } from '@/lib/auth/roles';
import { mainNavItems } from './nav-config';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout, hasPermission } = useAuth();
  const { theme, setTheme } = useTheme();

  const isActive = (href: string) => {
    if (href === '/dashboard') {
      return pathname === '/dashboard';
    }
    return pathname.startsWith(href);
  };

  const visibleItems = mainNavItems.filter((item) => {
    if (!item.permission) return true;
    return hasPermission(item.permission as Permission);
  });

  const userInitials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '??';

  const roleLabelMap: Record<string, string> = {
    viewer: 'Viewer',
    builder: 'Builder',
    builder_prod: 'Builder (Prod)',
    approver: 'Approver',
    admin: 'Admin',
  };

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'hidden md:flex flex-col border-r bg-card transition-all duration-300 ease-in-out',
          collapsed ? 'w-[68px]' : 'w-64'
        )}
      >
        {/* ---------------------------------------------------------------- */}
        {/* Brand                                                           */}
        {/* ---------------------------------------------------------------- */}
        <div
          className={cn(
            'flex h-16 items-center border-b px-4',
            collapsed ? 'justify-center' : 'gap-3'
          )}
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Hammer className="h-4 w-4" />
          </div>
          {!collapsed && (
            <span className="text-lg font-bold tracking-tight">AnvilOps</span>
          )}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Navigation                                                      */}
        {/* ---------------------------------------------------------------- */}
        <ScrollArea className="flex-1 py-4">
          <nav className="flex flex-col gap-1 px-3">
            {visibleItems.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;

              const linkContent = (
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    collapsed && 'justify-center px-0'
                  )}
                >
                  <Icon className={cn('h-4 w-4 shrink-0', active && 'text-primary')} />
                  {!collapsed && (
                    <>
                      <span className="flex-1">{item.title}</span>
                      {item.badge && (
                        <Badge
                          variant="secondary"
                          className="ml-auto h-5 min-w-[20px] justify-center px-1.5 text-[10px]"
                        >
                          {item.badge}
                        </Badge>
                      )}
                    </>
                  )}
                </Link>
              );

              if (collapsed) {
                return (
                  <Tooltip key={item.href}>
                    <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                    <TooltipContent side="right" className="font-medium">
                      {item.title}
                    </TooltipContent>
                  </Tooltip>
                );
              }

              return <div key={item.href}>{linkContent}</div>;
            })}
          </nav>
        </ScrollArea>

        {/* ---------------------------------------------------------------- */}
        {/* Bottom section: theme toggle, user, collapse                    */}
        {/* ---------------------------------------------------------------- */}
        <div className="mt-auto border-t">
          {/* Theme toggle */}
          <div className={cn('flex items-center px-3 py-2', collapsed && 'justify-center')}>
            {collapsed ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9"
                    onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                  >
                    <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
                    <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
                    <span className="sr-only">Toggle theme</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">Toggle theme</TooltipContent>
              </Tooltip>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start gap-3 text-muted-foreground hover:text-accent-foreground"
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              >
                <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
                <Moon className="absolute ml-0 h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
                <span className="ml-4">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
              </Button>
            )}
          </div>

          <Separator />

          {/* User info */}
          <div
            className={cn(
              'flex items-center gap-3 px-3 py-3',
              collapsed && 'justify-center px-0'
            )}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
              {userInitials}
            </div>
            {!collapsed && (
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium">{user?.name || 'User'}</p>
                <Badge variant="secondary" className="mt-0.5 text-[10px] px-1.5 py-0">
                  {roleLabelMap[user?.role || 'viewer']}
                </Badge>
              </div>
            )}
            {!collapsed && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                    onClick={logout}
                  >
                    <LogOut className="h-4 w-4" />
                    <span className="sr-only">Log out</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">Log out</TooltipContent>
              </Tooltip>
            )}
          </div>

          <Separator />

          {/* Collapse toggle */}
          <div className={cn('flex items-center px-3 py-2', collapsed && 'justify-center')}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    'text-muted-foreground hover:text-accent-foreground',
                    collapsed ? 'h-9 w-9 p-0' : 'w-full justify-start gap-3'
                  )}
                  onClick={() => setCollapsed(!collapsed)}
                >
                  {collapsed ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <>
                      <ChevronLeft className="h-4 w-4" />
                      <span>Collapse</span>
                    </>
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}
