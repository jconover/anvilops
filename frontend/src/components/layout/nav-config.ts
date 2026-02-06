import {
  Server,
  Plus,
  ClipboardList,
  CheckSquare,
  Shield,
  FileText,
  Bell,
  Settings,
  LayoutDashboard,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  permission?: string;
  badge?: string;
}

export const mainNavItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { title: 'New Server', href: '/dashboard/servers/new', icon: Plus, permission: 'servers:create' },
  { title: 'Servers', href: '/dashboard/servers', icon: Server },
  { title: 'Requests', href: '/dashboard/requests', icon: ClipboardList },
  { title: 'Approvals', href: '/dashboard/approvals', icon: CheckSquare, permission: 'servers:approve' },
  { title: 'Compliance', href: '/dashboard/compliance', icon: Shield },
  { title: 'Audit Log', href: '/dashboard/audit', icon: FileText, permission: 'admin:access' },
  { title: 'Notifications', href: '/dashboard/notifications', icon: Bell },
  { title: 'Admin', href: '/dashboard/admin', icon: Settings, permission: 'admin:access' },
];
