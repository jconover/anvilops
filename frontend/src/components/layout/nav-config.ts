import {
  Server,
  Plus,
  ClipboardList,
  CheckSquare,
  Shield,
  Radar,
  FileText,
  Bell,
  Settings,
  LayoutDashboard,
  Database,
  Layers,
  Calendar,
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
  { title: 'Drift Detection', href: '/dashboard/drift', icon: Radar },
  { title: 'Schedules', href: '/dashboard/schedules', icon: Calendar, permission: 'servers:create' },
  { title: 'Scaling', href: '/dashboard/scaling', icon: Layers, permission: 'servers:create' },
  { title: 'CMDB', href: '/dashboard/cmdb', icon: Database, permission: 'admin:access' },
  { title: 'Audit Log', href: '/dashboard/audit', icon: FileText, permission: 'admin:access' },
  { title: 'Notifications', href: '/dashboard/notifications', icon: Bell },
  { title: 'Admin', href: '/dashboard/admin', icon: Settings, permission: 'admin:access' },
];
