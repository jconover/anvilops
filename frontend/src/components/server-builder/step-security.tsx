'use client';

import { useState } from 'react';
import {
  Globe,
  Lock,
  Database,
  Settings2,
  Plus,
  X,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useServerForm } from '@/hooks/use-server-form';
import type { SecurityProfile } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Security profile options
// ---------------------------------------------------------------------------

const PROFILES: {
  value: SecurityProfile;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    value: 'web_facing',
    label: 'Web Facing',
    description: 'HTTP/HTTPS inbound from the internet. Outbound open. WAF recommended.',
    icon: Globe,
  },
  {
    value: 'internal_only',
    label: 'Internal Only',
    description: 'No public access. Reachable only from within the VPC or via VPN.',
    icon: Lock,
  },
  {
    value: 'database',
    label: 'Database',
    description: 'Restricted to application-tier security groups on DB ports only.',
    icon: Database,
  },
  {
    value: 'custom',
    label: 'Custom',
    description: 'Manually define security group rules after provisioning.',
    icon: Settings2,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepSecurity() {
  const security_profile = useServerForm((s) => s.security_profile);
  const domain_join = useServerForm((s) => s.domain_join);
  const tags = useServerForm((s) => s.tags);
  const setField = useServerForm((s) => s.setField);

  // Local state for the new tag inputs
  const [newTagKey, setNewTagKey] = useState('');
  const [newTagValue, setNewTagValue] = useState('');

  const addTag = () => {
    const key = newTagKey.trim();
    const value = newTagValue.trim();
    if (!key) return;
    setField('tags', { ...tags, [key]: value });
    setNewTagKey('');
    setNewTagValue('');
  };

  const removeTag = (key: string) => {
    const next = { ...tags };
    delete next[key];
    setField('tags', next);
  };

  return (
    <div className="space-y-8">
      {/* Security profile */}
      <fieldset className="space-y-3">
        <legend className="text-base font-semibold">Security Profile</legend>
        <p className="text-sm text-muted-foreground">
          Determines the security group rules applied to the server.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {PROFILES.map((profile) => {
            const Icon = profile.icon;
            const isSelected = security_profile === profile.value;
            return (
              <Card
                key={profile.value}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  isSelected && 'ring-2 ring-primary',
                )}
                onClick={() => setField('security_profile', profile.value)}
              >
                <CardContent className="flex items-start gap-4 p-5">
                  <div
                    className={cn(
                      'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">{profile.label}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {profile.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </fieldset>

      {/* Domain join */}
      <div className="space-y-3">
        <Label className="text-base font-semibold">Active Directory Domain Join</Label>
        <p className="text-sm text-muted-foreground">
          Join this server to the corporate Active Directory domain during provisioning.
        </p>
        <div className="flex items-center gap-3">
          <Switch
            id="domain_join"
            checked={domain_join}
            onCheckedChange={(checked) => setField('domain_join', checked)}
          />
          <Label htmlFor="domain_join" className="cursor-pointer text-sm">
            {domain_join ? 'Enabled' : 'Disabled'}
          </Label>
        </div>
      </div>

      {/* Tags */}
      <div className="space-y-3">
        <Label className="text-base font-semibold">Tags</Label>
        <p className="text-sm text-muted-foreground">
          Add custom key-value tags that will be applied to all AWS resources.
        </p>

        {/* Existing tags */}
        {Object.keys(tags).length > 0 && (
          <div className="space-y-2">
            {Object.entries(tags).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2"
              >
                <span className="text-sm font-medium">{key}</span>
                <span className="text-muted-foreground">=</span>
                <span className="text-sm">{value}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto h-7 w-7"
                  onClick={() => removeTag(key)}
                >
                  <X className="h-3.5 w-3.5" />
                  <span className="sr-only">Remove tag {key}</span>
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* New tag inputs */}
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="tag-key" className="text-xs text-muted-foreground">
              Key
            </Label>
            <Input
              id="tag-key"
              placeholder="e.g. CostCenter"
              value={newTagKey}
              onChange={(e) => setNewTagKey(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag();
                }
              }}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="tag-value" className="text-xs text-muted-foreground">
              Value
            </Label>
            <Input
              id="tag-value"
              placeholder="e.g. Engineering"
              value={newTagValue}
              onChange={(e) => setNewTagValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag();
                }
              }}
            />
          </div>
          <Button
            variant="outline"
            size="default"
            onClick={addTag}
            disabled={!newTagKey.trim()}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}
