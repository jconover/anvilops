'use client';

import { useState } from 'react';
import {
  Plus,
  X,
  HardDrive,
} from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { useServerForm, type StorageVolume } from '@/hooks/use-server-form';
import type { VolumeType, OsType } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Puppet role options
// ---------------------------------------------------------------------------

const PUPPET_ROLES = [
  { value: 'base', label: 'Base', description: 'Minimal OS hardening and monitoring agents' },
  { value: 'web_server', label: 'Web Server', description: 'Nginx/IIS configuration and TLS' },
  { value: 'db_server', label: 'Database Server', description: 'Database engine tuning and backups' },
  { value: 'app_server', label: 'Application Server', description: 'Runtime config and deploy hooks' },
  { value: 'dev_workstation', label: 'Dev Workstation', description: 'Developer tools and IDE config' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isWindowsOs(os: OsType): boolean {
  return os === 'windows_2022' || os === 'windows_2019';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepSoftware() {
  const puppet_role = useServerForm((s) => s.puppet_role);
  const software_packages = useServerForm((s) => s.software_packages);
  const additional_storage = useServerForm((s) => s.additional_storage);
  const os_type = useServerForm((s) => s.os_type);
  const setField = useServerForm((s) => s.setField);

  const isWindows = isWindowsOs(os_type);

  // Local state for package input
  const [newPackage, setNewPackage] = useState('');

  const addPackage = () => {
    const pkg = newPackage.trim();
    if (!pkg || software_packages.includes(pkg)) return;
    setField('software_packages', [...software_packages, pkg]);
    setNewPackage('');
  };

  const removePackage = (pkg: string) => {
    setField(
      'software_packages',
      software_packages.filter((p) => p !== pkg),
    );
  };

  // Storage volume management
  const addVolume = () => {
    const newVol: StorageVolume = isWindows
      ? { drive_letter: 'D', size_gb: 50, volume_type: 'gp3' }
      : { mount_point: '/data', size_gb: 50, volume_type: 'gp3' };
    setField('additional_storage', [...additional_storage, newVol]);
  };

  const updateVolume = (index: number, patch: Partial<StorageVolume>) => {
    const updated = additional_storage.map((vol, i) =>
      i === index ? { ...vol, ...patch } : vol,
    );
    setField('additional_storage', updated);
  };

  const removeVolume = (index: number) => {
    setField(
      'additional_storage',
      additional_storage.filter((_, i) => i !== index),
    );
  };

  return (
    <div className="space-y-8">
      {/* Puppet role */}
      <div className="space-y-3">
        <Label htmlFor="puppet_role" className="text-base font-semibold">
          Puppet Role
        </Label>
        <p className="text-sm text-muted-foreground">
          Determines the compliance profile and Day 2 configuration applied by Puppet Enterprise.
        </p>
        <Select
          value={puppet_role}
          onValueChange={(val) => setField('puppet_role', val)}
        >
          <SelectTrigger id="puppet_role" className="max-w-md">
            <SelectValue placeholder="Select a role" />
          </SelectTrigger>
          <SelectContent>
            {PUPPET_ROLES.map((role) => (
              <SelectItem key={role.value} value={role.value}>
                <div className="flex flex-col">
                  <span>{role.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {role.description}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Software packages */}
      <div className="space-y-3">
        <Label className="text-base font-semibold">Software Packages</Label>
        <p className="text-sm text-muted-foreground">
          Packages to install during the Ansible configuration step.
        </p>

        {/* Current packages */}
        {software_packages.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {software_packages.map((pkg) => (
              <Badge
                key={pkg}
                variant="secondary"
                className="gap-1.5 py-1 pl-3 pr-1.5"
              >
                {pkg}
                <button
                  type="button"
                  onClick={() => removePackage(pkg)}
                  className="rounded-full p-0.5 hover:bg-muted-foreground/20"
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Remove {pkg}</span>
                </button>
              </Badge>
            ))}
          </div>
        )}

        {/* Add package */}
        <div className="flex items-end gap-2">
          <div className="max-w-md flex-1 space-y-1">
            <Input
              placeholder="e.g. nginx, docker, git"
              value={newPackage}
              onChange={(e) => setNewPackage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addPackage();
                }
              }}
            />
          </div>
          <Button
            variant="outline"
            onClick={addPackage}
            disabled={!newPackage.trim()}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Add Package
          </Button>
        </div>
      </div>

      <Separator />

      {/* Additional storage */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <Label className="text-base font-semibold">Additional Storage Volumes</Label>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Add extra EBS volumes beyond the root volume.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={addVolume}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Volume
          </Button>
        </div>

        {additional_storage.length === 0 && (
          <p className="text-sm italic text-muted-foreground">
            No additional volumes configured. Only the root volume will be created.
          </p>
        )}

        <div className="space-y-3">
          {additional_storage.map((vol, index) => (
            <Card key={index}>
              <CardContent className="flex flex-wrap items-end gap-4 p-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <HardDrive className="h-4 w-4" />
                </div>

                {/* Drive letter or mount point */}
                {isWindows ? (
                  <div className="w-24 space-y-1">
                    <Label className="text-xs text-muted-foreground">
                      Drive Letter
                    </Label>
                    <Input
                      value={vol.drive_letter ?? ''}
                      onChange={(e) =>
                        updateVolume(index, {
                          drive_letter: e.target.value.toUpperCase().slice(0, 1),
                        })
                      }
                      maxLength={1}
                      placeholder="D"
                    />
                  </div>
                ) : (
                  <div className="min-w-[10rem] flex-1 space-y-1">
                    <Label className="text-xs text-muted-foreground">
                      Mount Point
                    </Label>
                    <Input
                      value={vol.mount_point ?? ''}
                      onChange={(e) =>
                        updateVolume(index, { mount_point: e.target.value })
                      }
                      placeholder="/data"
                    />
                  </div>
                )}

                {/* Size */}
                <div className="w-28 space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    Size (GB)
                  </Label>
                  <Input
                    type="number"
                    min={1}
                    max={16384}
                    value={vol.size_gb}
                    onChange={(e) =>
                      updateVolume(index, {
                        size_gb: Math.max(1, parseInt(e.target.value) || 1),
                      })
                    }
                  />
                </div>

                {/* Volume type */}
                <div className="w-32 space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    Volume Type
                  </Label>
                  <Select
                    value={vol.volume_type}
                    onValueChange={(val: VolumeType) =>
                      updateVolume(index, { volume_type: val })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gp3">gp3</SelectItem>
                      <SelectItem value="io2">io2</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Remove */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 shrink-0 text-destructive hover:text-destructive"
                  onClick={() => removeVolume(index)}
                >
                  <X className="h-4 w-4" />
                  <span className="sr-only">Remove volume {index + 1}</span>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
