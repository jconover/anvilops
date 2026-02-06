'use client';

import { useState } from 'react';
import { Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';

interface SettingsState {
  apiBaseUrl: string;
  apiTimeout: string;
  complianceRefreshInterval: string;
  serverListRefreshInterval: string;
  buildPipelineRefreshInterval: string;
  slackWebhookUrl: string;
  slackNotificationsEnabled: boolean;
  emailNotificationsEnabled: boolean;
  notifyOnBuildComplete: boolean;
  notifyOnBuildFailure: boolean;
  notifyOnApprovalRequired: boolean;
  notifyOnComplianceFailure: boolean;
}

const DEFAULT_SETTINGS: SettingsState = {
  apiBaseUrl: 'http://localhost:8000/api/v1',
  apiTimeout: '30',
  complianceRefreshInterval: '30',
  serverListRefreshInterval: '10',
  buildPipelineRefreshInterval: '5',
  slackWebhookUrl: '',
  slackNotificationsEnabled: false,
  emailNotificationsEnabled: true,
  notifyOnBuildComplete: true,
  notifyOnBuildFailure: true,
  notifyOnApprovalRequired: true,
  notifyOnComplianceFailure: true,
};

export function SettingsPanel() {
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);

  function updateSetting<K extends keyof SettingsState>(
    key: K,
    value: SettingsState[K],
  ) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setIsSaving(true);
    // Simulate save delay
    await new Promise((resolve) => setTimeout(resolve, 800));
    setIsSaving(false);
    toast.success('Settings saved successfully.');
  }

  return (
    <div className="space-y-6">
      {/* API Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">API Configuration</CardTitle>
          <CardDescription>
            Configure the connection to the AnvilOps backend API.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api-base-url">Base URL</Label>
            <Input
              id="api-base-url"
              value={settings.apiBaseUrl}
              onChange={(e) => updateSetting('apiBaseUrl', e.target.value)}
              placeholder="http://localhost:8000/api/v1"
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="api-timeout">Request Timeout (seconds)</Label>
            <Select
              value={settings.apiTimeout}
              onValueChange={(value) => updateSetting('apiTimeout', value)}
            >
              <SelectTrigger id="api-timeout">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10 seconds</SelectItem>
                <SelectItem value="30">30 seconds</SelectItem>
                <SelectItem value="60">60 seconds</SelectItem>
                <SelectItem value="120">120 seconds</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Polling Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Polling Intervals</CardTitle>
          <CardDescription>
            Control how frequently the UI refreshes data from the API.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="compliance-interval">Compliance Dashboard</Label>
              <Select
                value={settings.complianceRefreshInterval}
                onValueChange={(value) =>
                  updateSetting('complianceRefreshInterval', value)
                }
              >
                <SelectTrigger id="compliance-interval">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15 seconds</SelectItem>
                  <SelectItem value="30">30 seconds</SelectItem>
                  <SelectItem value="60">60 seconds</SelectItem>
                  <SelectItem value="300">5 minutes</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="server-list-interval">Server List</Label>
              <Select
                value={settings.serverListRefreshInterval}
                onValueChange={(value) =>
                  updateSetting('serverListRefreshInterval', value)
                }
              >
                <SelectTrigger id="server-list-interval">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5 seconds</SelectItem>
                  <SelectItem value="10">10 seconds</SelectItem>
                  <SelectItem value="30">30 seconds</SelectItem>
                  <SelectItem value="60">60 seconds</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pipeline-interval">Build Pipeline</Label>
              <Select
                value={settings.buildPipelineRefreshInterval}
                onValueChange={(value) =>
                  updateSetting('buildPipelineRefreshInterval', value)
                }
              >
                <SelectTrigger id="pipeline-interval">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="3">3 seconds</SelectItem>
                  <SelectItem value="5">5 seconds</SelectItem>
                  <SelectItem value="10">10 seconds</SelectItem>
                  <SelectItem value="30">30 seconds</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notification Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notifications</CardTitle>
          <CardDescription>
            Configure Slack and email notification preferences.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="slack-webhook">Slack Webhook URL</Label>
            <Input
              id="slack-webhook"
              type="url"
              value={settings.slackWebhookUrl}
              onChange={(e) =>
                updateSetting('slackWebhookUrl', e.target.value)
              }
              placeholder="https://hooks.slack.com/services/..."
              className="font-mono text-sm"
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="slack-enabled">Slack Notifications</Label>
              <p className="text-xs text-muted-foreground">
                Send notifications to the configured Slack channel.
              </p>
            </div>
            <Switch
              id="slack-enabled"
              checked={settings.slackNotificationsEnabled}
              onCheckedChange={(checked) =>
                updateSetting('slackNotificationsEnabled', checked)
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="email-enabled">Email Notifications</Label>
              <p className="text-xs text-muted-foreground">
                Send notifications via email to requesting users.
              </p>
            </div>
            <Switch
              id="email-enabled"
              checked={settings.emailNotificationsEnabled}
              onCheckedChange={(checked) =>
                updateSetting('emailNotificationsEnabled', checked)
              }
            />
          </div>

          <Separator />

          <p className="text-sm font-medium">Notification Triggers</p>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label htmlFor="notify-build-complete" className="font-normal">
                Build completed successfully
              </Label>
              <Switch
                id="notify-build-complete"
                checked={settings.notifyOnBuildComplete}
                onCheckedChange={(checked) =>
                  updateSetting('notifyOnBuildComplete', checked)
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="notify-build-failure" className="font-normal">
                Build failed
              </Label>
              <Switch
                id="notify-build-failure"
                checked={settings.notifyOnBuildFailure}
                onCheckedChange={(checked) =>
                  updateSetting('notifyOnBuildFailure', checked)
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="notify-approval" className="font-normal">
                Approval required
              </Label>
              <Switch
                id="notify-approval"
                checked={settings.notifyOnApprovalRequired}
                onCheckedChange={(checked) =>
                  updateSetting('notifyOnApprovalRequired', checked)
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="notify-compliance" className="font-normal">
                Compliance failure detected
              </Label>
              <Switch
                id="notify-compliance"
                checked={settings.notifyOnComplianceFailure}
                onCheckedChange={(checked) =>
                  updateSetting('notifyOnComplianceFailure', checked)
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving} className="gap-2">
          <Save className="h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save Settings'}
        </Button>
      </div>
    </div>
  );
}
