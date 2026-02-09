'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Clock, AlertCircle } from 'lucide-react';

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

interface CronPreset {
  label: string;
  cron: string;
  description: string;
}

const CRON_PRESETS: CronPreset[] = [
  { label: 'Daily at 2 AM', cron: '0 2 * * *', description: 'Runs every day at 2:00 AM' },
  { label: 'Weekly Monday', cron: '0 6 * * 1', description: 'Runs every Monday at 6:00 AM' },
  { label: 'Weekdays 6 AM', cron: '0 6 * * 1-5', description: 'Runs Monday through Friday at 6:00 AM' },
  { label: 'Monthly 1st', cron: '0 3 1 * *', description: 'Runs on the 1st of every month at 3:00 AM' },
];

// ---------------------------------------------------------------------------
// Field options
// ---------------------------------------------------------------------------

const MINUTE_OPTIONS = [
  { value: '*', label: 'Every minute' },
  { value: '0', label: '0' },
  { value: '5', label: '5' },
  { value: '10', label: '10' },
  { value: '15', label: '15' },
  { value: '20', label: '20' },
  { value: '30', label: '30' },
  { value: '45', label: '45' },
];

const HOUR_OPTIONS = [
  { value: '*', label: 'Every hour' },
  ...Array.from({ length: 24 }, (_, i) => ({
    value: String(i),
    label: `${i.toString().padStart(2, '0')}:00`,
  })),
];

const DAY_OF_MONTH_OPTIONS = [
  { value: '*', label: 'Every day' },
  { value: '1', label: '1st' },
  { value: '15', label: '15th' },
  ...Array.from({ length: 31 }, (_, i) => ({
    value: String(i + 1),
    label: String(i + 1),
  })).filter((o) => o.value !== '1' && o.value !== '15'),
];

const MONTH_OPTIONS = [
  { value: '*', label: 'Every month' },
  { value: '1', label: 'January' },
  { value: '2', label: 'February' },
  { value: '3', label: 'March' },
  { value: '4', label: 'April' },
  { value: '5', label: 'May' },
  { value: '6', label: 'June' },
  { value: '7', label: 'July' },
  { value: '8', label: 'August' },
  { value: '9', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
];

const DAY_OF_WEEK_OPTIONS = [
  { value: '*', label: 'Every day' },
  { value: '1-5', label: 'Weekdays (Mon-Fri)' },
  { value: '0,6', label: 'Weekends (Sat-Sun)' },
  { value: '0', label: 'Sunday' },
  { value: '1', label: 'Monday' },
  { value: '2', label: 'Tuesday' },
  { value: '3', label: 'Wednesday' },
  { value: '4', label: 'Thursday' },
  { value: '5', label: 'Friday' },
  { value: '6', label: 'Saturday' },
];

// ---------------------------------------------------------------------------
// Cron description helper
// ---------------------------------------------------------------------------

const DAY_NAMES: Record<string, string> = {
  '0': 'Sunday',
  '1': 'Monday',
  '2': 'Tuesday',
  '3': 'Wednesday',
  '4': 'Thursday',
  '5': 'Friday',
  '6': 'Saturday',
};

const MONTH_NAMES: Record<string, string> = {
  '1': 'January',
  '2': 'February',
  '3': 'March',
  '4': 'April',
  '5': 'May',
  '6': 'June',
  '7': 'July',
  '8': 'August',
  '9': 'September',
  '10': 'October',
  '11': 'November',
  '12': 'December',
};

function ordinalSuffix(n: number): string {
  const j = n % 10;
  const k = n % 100;
  if (j === 1 && k !== 11) return `${n}st`;
  if (j === 2 && k !== 12) return `${n}nd`;
  if (j === 3 && k !== 13) return `${n}rd`;
  return `${n}th`;
}

/**
 * Build a human-readable description from a 5-field cron expression.
 * This is a best-effort description covering common patterns.
 */
export function describeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return 'Invalid cron expression';

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  const segments: string[] = [];

  // Time portion
  if (minute === '*' && hour === '*') {
    segments.push('Runs every minute');
  } else if (minute === '*') {
    segments.push(`Runs every minute of hour ${hour}`);
  } else if (hour === '*') {
    segments.push(`Runs at minute ${minute} of every hour`);
  } else {
    const h = parseInt(hour, 10);
    const m = parseInt(minute, 10);
    if (isNaN(h) || isNaN(m)) {
      segments.push(`Runs at ${hour}:${minute.padStart(2, '0')}`);
    } else {
      const period = h >= 12 ? 'PM' : 'AM';
      const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
      segments.push(
        `Runs at ${displayHour}:${m.toString().padStart(2, '0')} ${period}`,
      );
    }
  }

  // Day of week
  if (dayOfWeek !== '*') {
    if (dayOfWeek === '1-5') {
      segments.push('on weekdays');
    } else if (dayOfWeek === '0,6') {
      segments.push('on weekends');
    } else {
      const names = dayOfWeek.split(',').map((d) => DAY_NAMES[d] || d);
      segments.push(`on ${names.join(', ')}`);
    }
  }

  // Day of month
  if (dayOfMonth !== '*') {
    const d = parseInt(dayOfMonth, 10);
    if (!isNaN(d)) {
      segments.push(`on the ${ordinalSuffix(d)}`);
    } else {
      segments.push(`on day ${dayOfMonth}`);
    }
  }

  // Month
  if (month !== '*') {
    const monthNames = month
      .split(',')
      .map((m) => MONTH_NAMES[m] || m);
    segments.push(`in ${monthNames.join(', ')}`);
  }

  return segments.join(' ');
}

/**
 * Validate a cron expression (5-field format).
 * Returns null if valid, or an error message string.
 */
export function validateCron(cron: string): string | null {
  if (!cron.trim()) return 'Cron expression is required';

  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) {
    return 'Cron expression must have exactly 5 fields (minute hour day month weekday)';
  }

  const fieldPatterns = [
    { name: 'Minute', min: 0, max: 59 },
    { name: 'Hour', min: 0, max: 23 },
    { name: 'Day of month', min: 1, max: 31 },
    { name: 'Month', min: 1, max: 12 },
    { name: 'Day of week', min: 0, max: 6 },
  ];

  // Regex that matches individual cron field syntax
  const fieldRegex = /^(\*|(\d+(-\d+)?(,\d+(-\d+)?)*)(\/\d+)?)$/;

  for (let i = 0; i < 5; i++) {
    const field = parts[i];
    const spec = fieldPatterns[i];

    // Allow * and */N
    if (field === '*' || /^\*\/\d+$/.test(field)) continue;

    if (!fieldRegex.test(field)) {
      return `${spec.name} field "${field}" has invalid syntax`;
    }

    // Check numeric ranges for simple values
    const values = field.replace(/\/\d+$/, '').split(',');
    for (const v of values) {
      const rangeParts = v.split('-');
      for (const rp of rangeParts) {
        const n = parseInt(rp, 10);
        if (!isNaN(n) && (n < spec.min || n > spec.max)) {
          return `${spec.name} value ${n} is out of range (${spec.min}-${spec.max})`;
        }
      }
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type CronMode = 'preset' | 'custom';

interface CronBuilderProps {
  value: string;
  onChange: (cron: string) => void;
  className?: string;
}

export function CronBuilder({ value, onChange, className }: CronBuilderProps) {
  const [mode, setMode] = useState<CronMode>('preset');
  const [customInput, setCustomInput] = useState(value || '0 2 * * *');

  // Parse current cron into individual fields for the custom builder
  const fields = useMemo(() => {
    const parts = (value || '0 2 * * *').trim().split(/\s+/);
    if (parts.length !== 5) return ['0', '2', '*', '*', '*'];
    return parts;
  }, [value]);

  const [minute, setMinute] = useState(fields[0]);
  const [hour, setHour] = useState(fields[1]);
  const [dayOfMonth, setDayOfMonth] = useState(fields[2]);
  const [month, setMonth] = useState(fields[3]);
  const [dayOfWeek, setDayOfWeek] = useState(fields[4]);

  // Check if current value matches any preset
  const activePreset = useMemo(
    () => CRON_PRESETS.find((p) => p.cron === value),
    [value],
  );

  // Sync fields when value changes externally
  useEffect(() => {
    const parts = (value || '0 2 * * *').trim().split(/\s+/);
    if (parts.length === 5) {
      setMinute(parts[0]);
      setHour(parts[1]);
      setDayOfMonth(parts[2]);
      setMonth(parts[3]);
      setDayOfWeek(parts[4]);
      setCustomInput(value);
    }
  }, [value]);

  // Build cron from individual fields and propagate changes
  const updateFromFields = useCallback(
    (min: string, hr: string, dom: string, mon: string, dow: string) => {
      const cron = `${min} ${hr} ${dom} ${mon} ${dow}`;
      setCustomInput(cron);
      onChange(cron);
    },
    [onChange],
  );

  const handlePresetSelect = (preset: CronPreset) => {
    setMode('preset');
    onChange(preset.cron);
    setCustomInput(preset.cron);
  };

  const handleCustomInputChange = (raw: string) => {
    setCustomInput(raw);
    const trimmed = raw.trim();
    if (trimmed.split(/\s+/).length === 5) {
      onChange(trimmed);
    }
  };

  const handleFieldChange = (
    field: 'minute' | 'hour' | 'dayOfMonth' | 'month' | 'dayOfWeek',
    val: string,
  ) => {
    const newMin = field === 'minute' ? val : minute;
    const newHour = field === 'hour' ? val : hour;
    const newDom = field === 'dayOfMonth' ? val : dayOfMonth;
    const newMon = field === 'month' ? val : month;
    const newDow = field === 'dayOfWeek' ? val : dayOfWeek;

    if (field === 'minute') setMinute(val);
    if (field === 'hour') setHour(val);
    if (field === 'dayOfMonth') setDayOfMonth(val);
    if (field === 'month') setMonth(val);
    if (field === 'dayOfWeek') setDayOfWeek(val);

    updateFromFields(newMin, newHour, newDom, newMon, newDow);
  };

  const validationError = validateCron(value || '');
  const description = !validationError ? describeCron(value || '') : null;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Mode selector / Preset buttons */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Schedule Frequency</Label>
        <div className="flex flex-wrap gap-2">
          {CRON_PRESETS.map((preset) => (
            <Button
              key={preset.cron}
              type="button"
              variant={activePreset?.cron === preset.cron ? 'default' : 'outline'}
              size="sm"
              onClick={() => handlePresetSelect(preset)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            type="button"
            variant={mode === 'custom' && !activePreset ? 'default' : 'outline'}
            size="sm"
            onClick={() => setMode('custom')}
          >
            Custom
          </Button>
        </div>
      </div>

      {/* Custom cron builder */}
      {mode === 'custom' && !activePreset && (
        <div className="space-y-4 rounded-lg border p-4">
          {/* Visual field selectors */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Minute</Label>
              <Select value={minute} onValueChange={(v) => handleFieldChange('minute', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MINUTE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Hour</Label>
              <Select value={hour} onValueChange={(v) => handleFieldChange('hour', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOUR_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Day of Month</Label>
              <Select value={dayOfMonth} onValueChange={(v) => handleFieldChange('dayOfMonth', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAY_OF_MONTH_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Month</Label>
              <Select value={month} onValueChange={(v) => handleFieldChange('month', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MONTH_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Day of Week</Label>
              <Select value={dayOfWeek} onValueChange={(v) => handleFieldChange('dayOfWeek', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAY_OF_WEEK_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Raw cron input */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">
              Cron Expression (advanced)
            </Label>
            <Input
              value={customInput}
              onChange={(e) => handleCustomInputChange(e.target.value)}
              placeholder="0 2 * * *"
              className="font-mono text-sm"
            />
          </div>
        </div>
      )}

      {/* Live preview */}
      <div
        className={cn(
          'flex items-start gap-2 rounded-lg border p-3',
          validationError
            ? 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30'
            : 'border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/30',
        )}
      >
        {validationError ? (
          <>
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-300">
                Invalid expression
              </p>
              <p className="text-xs text-red-600 dark:text-red-400">
                {validationError}
              </p>
            </div>
          </>
        ) : (
          <>
            <Clock className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-300">
                {description}
              </p>
              <p className="mt-0.5 text-xs text-blue-600 dark:text-blue-400 font-mono">
                {value || '(none)'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
