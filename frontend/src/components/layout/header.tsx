'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Menu,
  Search,
  Bell,
  User,
  Settings,
  LogOut,
  Hammer,
  Moon,
  Sun,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth/context';
import type { Permission } from '@/lib/auth/roles';
import { mainNavItems } from './nav-config';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';

/**
 * Map of route prefixes to page titles.
 * The header displays a contextual title based on the current route.
 */
const ROUTE_TITLES: Record<string, string> = {
  '/dashboard/servers/new': 'New Server',
  '/dashboard/servers': 'Servers',
  '/dashboard/requests': 'Requests',
  '/dashboard/approvals': 'Approvals',
  '/dashboard/compliance': 'Compliance',
  '/dashboard/admin': 'Admin',
  '/dashboard': 'Dashboard',
};

function getPageTitle(pathname: string): string {
  // Try most specific match first (longest prefix)
  const sorted = Object.entries(ROUTE_TITLES).sort(
    (a, b) => b[0].length - a[0].length
  );
  for (const [prefix, title] of sorted) {
    if (pathname.startsWith(prefix)) return title;
  }
  return 'Dashboard';
}

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, hasPermission } = useAuth();
  const { theme, setTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  const pageTitle = getPageTitle(pathname);

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
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
    <header className="flex h-16 shrink-0 items-center gap-4 border-b bg-card px-4 md:px-6">
      {/* Mobile menu trigger */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="md:hidden">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="border-b px-4 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Hammer className="h-4 w-4" />
              </div>
              <SheetTitle className="text-lg font-bold">AnvilOps</SheetTitle>
            </div>
            <SheetDescription className="sr-only">
              Navigation menu
            </SheetDescription>
          </SheetHeader>
          <ScrollArea className="flex-1 py-4">
            <nav className="flex flex-col gap-1 px-3">
              {visibleItems.map((item) => {
                const active = isActive(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                      active
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <Icon className={cn('h-4 w-4 shrink-0', active && 'text-primary')} />
                    <span className="flex-1">{item.title}</span>
                    {item.badge && (
                      <Badge
                        variant="secondary"
                        className="ml-auto h-5 min-w-[20px] justify-center px-1.5 text-[10px]"
                      >
                        {item.badge}
                      </Badge>
                    )}
                  </Link>
                );
              })}
            </nav>
          </ScrollArea>

          <Separator />

          {/* Mobile: theme toggle */}
          <div className="px-3 py-3">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-3 text-muted-foreground"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute ml-0 h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
              <span className="ml-4">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
            </Button>
          </div>

          <Separator />

          {/* Mobile: user info */}
          <div className="flex items-center gap-3 px-4 py-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
              {userInitials}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="truncate text-sm font-medium">{user?.name || 'User'}</p>
              <Badge variant="secondary" className="mt-0.5 text-[10px] px-1.5 py-0">
                {roleLabelMap[user?.role || 'viewer']}
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 text-muted-foreground"
              onClick={() => {
                setMobileOpen(false);
                logout();
              }}
            >
              <LogOut className="h-4 w-4" />
              <span className="sr-only">Log out</span>
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Page title */}
      <h2 className="text-lg font-semibold">{pageTitle}</h2>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Search (cosmetic) */}
      <div className="hidden md:flex relative w-64">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search servers..."
          className="pl-9 h-9 bg-background"
          readOnly
        />
      </div>

      {/* Notification bell (cosmetic) */}
      <Button variant="ghost" size="icon" className="relative">
        <Bell className="h-5 w-5" />
        <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
        </span>
        <span className="sr-only">Notifications</span>
      </Button>

      {/* User dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-9 w-9 rounded-full">
            <Avatar className="h-9 w-9">
              <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                {userInitials}
              </AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end" forceMount>
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">{user?.name || 'User'}</p>
              <p className="text-xs leading-none text-muted-foreground">{user?.email || ''}</p>
              <Badge variant="secondary" className="mt-1.5 w-fit text-[10px] px-1.5 py-0">
                {roleLabelMap[user?.role || 'viewer']}
              </Badge>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push('/dashboard/profile')}>
            <User className="mr-2 h-4 w-4" />
            <span>Profile</span>
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push('/dashboard/settings')}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            <span>Log out</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
