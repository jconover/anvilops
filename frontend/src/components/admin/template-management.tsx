'use client';

import { useState } from 'react';
import { Pencil, Server, Monitor, Database, Code2, Globe, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';

interface ServerTemplate {
  id: string;
  name: string;
  description: string;
  defaultOs: string;
  instanceSize: string;
  puppetRole: string;
  icon: React.ReactNode;
}

const TEMPLATES: ServerTemplate[] = [
  {
    id: 'standard-web',
    name: 'Standard Web Server',
    description: 'Internal web server with IIS or Nginx, standard hardening, monitoring agents.',
    defaultOs: 'windows_2022',
    instanceSize: 'medium',
    puppetRole: 'role::web_server',
    icon: <Server className="h-5 w-5" />,
  },
  {
    id: 'public-web',
    name: 'Public Web Server',
    description: 'Internet-facing web server with WAF integration, TLS termination, enhanced logging.',
    defaultOs: 'amazon_linux_2023',
    instanceSize: 'large',
    puppetRole: 'role::public_web',
    icon: <Globe className="h-5 w-5" />,
  },
  {
    id: 'sql-server',
    name: 'SQL Server',
    description: 'Microsoft SQL Server with optimized storage, backup agents, and database hardening.',
    defaultOs: 'windows_2022',
    instanceSize: 'large',
    puppetRole: 'role::sql_server',
    icon: <Database className="h-5 w-5" />,
  },
  {
    id: 'app-dotnet',
    name: 'App Server (.NET)',
    description: '.NET application server with IIS, .NET runtime, and application performance monitoring.',
    defaultOs: 'windows_2022',
    instanceSize: 'medium',
    puppetRole: 'role::app_dotnet',
    icon: <Code2 className="h-5 w-5" />,
  },
  {
    id: 'app-java',
    name: 'App Server (Java)',
    description: 'Java application server with JDK, Tomcat/WildFly, and JVM monitoring.',
    defaultOs: 'amazon_linux_2023',
    instanceSize: 'medium',
    puppetRole: 'role::app_java',
    icon: <Code2 className="h-5 w-5" />,
  },
  {
    id: 'dev-workstation',
    name: 'Dev Workstation',
    description: 'Developer workstation with IDE tools, SDKs, Docker, and relaxed security profile.',
    defaultOs: 'ubuntu_2204',
    instanceSize: 'medium',
    puppetRole: 'role::dev_workstation',
    icon: <Monitor className="h-5 w-5" />,
  },
];

function formatOsLabel(os: string): string {
  const labels: Record<string, string> = {
    windows_2022: 'Windows Server 2022',
    windows_2019: 'Windows Server 2019',
    amazon_linux_2023: 'Amazon Linux 2023',
    ubuntu_2204: 'Ubuntu 22.04',
    rhel_9: 'RHEL 9',
  };
  return labels[os] || os;
}

function formatSizeLabel(size: string): string {
  return size.charAt(0).toUpperCase() + size.slice(1);
}

export function TemplateManagement() {
  const [editingTemplate, setEditingTemplate] = useState<ServerTemplate | null>(null);
  const [formState, setFormState] = useState<Partial<ServerTemplate>>({});

  function handleEdit(template: ServerTemplate) {
    setEditingTemplate(template);
    setFormState({
      name: template.name,
      description: template.description,
      defaultOs: template.defaultOs,
      instanceSize: template.instanceSize,
      puppetRole: template.puppetRole,
    });
  }

  function handleSave() {
    toast.success(`Template "${formState.name}" updated successfully.`);
    setEditingTemplate(null);
    setFormState({});
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {TEMPLATES.map((template) => (
          <Card key={template.id} className="relative">
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-primary/10 p-2 text-primary">
                    {template.icon}
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold">{template.name}</h3>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                      {template.description}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  onClick={() => handleEdit(template)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                  <span className="sr-only">Edit template</span>
                </Button>
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                <Badge variant="outline" className="text-xs">
                  {formatOsLabel(template.defaultOs)}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {formatSizeLabel(template.instanceSize)}
                </Badge>
                <Badge variant="secondary" className="font-mono text-xs">
                  {template.puppetRole}
                </Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog
        open={editingTemplate !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingTemplate(null);
            setFormState({});
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              Edit Template
            </DialogTitle>
            <DialogDescription>
              Modify the default values for this server template.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="template-name">Template Name</Label>
              <Input
                id="template-name"
                value={formState.name || ''}
                onChange={(e) =>
                  setFormState((prev) => ({ ...prev, name: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template-description">Description</Label>
              <Input
                id="template-description"
                value={formState.description || ''}
                onChange={(e) =>
                  setFormState((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="template-os">Default OS</Label>
                <Select
                  value={formState.defaultOs}
                  onValueChange={(value) =>
                    setFormState((prev) => ({ ...prev, defaultOs: value }))
                  }
                >
                  <SelectTrigger id="template-os">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="windows_2022">Windows Server 2022</SelectItem>
                    <SelectItem value="windows_2019">Windows Server 2019</SelectItem>
                    <SelectItem value="amazon_linux_2023">Amazon Linux 2023</SelectItem>
                    <SelectItem value="ubuntu_2204">Ubuntu 22.04</SelectItem>
                    <SelectItem value="rhel_9">RHEL 9</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="template-size">Instance Size</Label>
                <Select
                  value={formState.instanceSize}
                  onValueChange={(value) =>
                    setFormState((prev) => ({ ...prev, instanceSize: value }))
                  }
                >
                  <SelectTrigger id="template-size">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Small</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="large">Large</SelectItem>
                    <SelectItem value="xl">XL</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="template-puppet-role">Puppet Role</Label>
              <Input
                id="template-puppet-role"
                value={formState.puppetRole || ''}
                onChange={(e) =>
                  setFormState((prev) => ({
                    ...prev,
                    puppetRole: e.target.value,
                  }))
                }
                className="font-mono text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEditingTemplate(null);
                setFormState({});
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleSave}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
