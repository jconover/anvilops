'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  X,
  Calendar,
  Filter,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Label } from '@/components/ui/label';
import { useAuditActions } from '@/lib/api/audit';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuditFilterState {
  dateRange: 'all' | '24h' | '7d' | '30d' | 'custom';
  startDate: string;
  endDate: string;
  action: string;
  category: string;
  actorEmail: string;
  status: string;
}

export const DEFAULT_FILTERS: AuditFilterState = {
  dateRange: '30d',
  startDate: '',
  endDate: '',
  action: '',
  category: '',
  actorEmail: '',
  status: '',
};

interface AuditFiltersProps {
  filters: AuditFilterState;
  onFiltersChange: (filters: AuditFilterState) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DATE_RANGE_OPTIONS = [
  { value: '24h', label: 'Last 24h' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'all', label: 'All time' },
  { value: 'custom', label: 'Custom' },
] as const;

const CATEGORY_OPTIONS = [
  { value: '', label: 'All Categories' },
  { value: 'server', label: 'Server' },
  { value: 'template', label: 'Template' },
  { value: 'auth', label: 'Authentication' },
  { value: 'system', label: 'System' },
] as const;

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'success', label: 'Success' },
  { value: 'failure', label: 'Failure' },
  { value: 'error', label: 'Error' },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AuditFilters({ filters, onFiltersChange }: AuditFiltersProps) {
  const { data: actionTypes } = useAuditActions();

  // Debounced actor email input
  const [emailInput, setEmailInput] = useState(filters.actorEmail);

  useEffect(() => {
    setEmailInput(filters.actorEmail);
  }, [filters.actorEmail]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (emailInput !== filters.actorEmail) {
        onFiltersChange({ ...filters, actorEmail: emailInput });
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [emailInput]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateFilter = useCallback(
    <K extends keyof AuditFilterState>(key: K, value: AuditFilterState[K]) => {
      onFiltersChange({ ...filters, [key]: value });
    },
    [filters, onFiltersChange],
  );

  // Count active filters (excluding dateRange since it always has a value)
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.action) count++;
    if (filters.category) count++;
    if (filters.actorEmail) count++;
    if (filters.status) count++;
    if (filters.dateRange === 'custom' && (filters.startDate || filters.endDate)) count++;
    return count;
  }, [filters]);

  const clearAll = useCallback(() => {
    setEmailInput('');
    onFiltersChange(DEFAULT_FILTERS);
  }, [onFiltersChange]);

  return (
    <div className="space-y-3">
      {/* Row 1: Date range presets */}
      <div className="flex flex-wrap items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        {DATE_RANGE_OPTIONS.map((option) => (
          <Button
            key={option.value}
            variant={filters.dateRange === option.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              if (option.value !== 'custom') {
                updateFilter('dateRange', option.value);
              } else {
                updateFilter('dateRange', 'custom');
              }
            }}
          >
            {option.label}
          </Button>
        ))}

        {/* Custom date range popover */}
        {filters.dateRange === 'custom' && (
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                {filters.startDate && filters.endDate
                  ? `${filters.startDate} - ${filters.endDate}`
                  : 'Select dates'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80" align="start">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="start-date" className="text-xs">
                    Start Date
                  </Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={filters.startDate}
                    onChange={(e) => updateFilter('startDate', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="end-date" className="text-xs">
                    End Date
                  </Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={filters.endDate}
                    onChange={(e) => updateFilter('endDate', e.target.value)}
                  />
                </div>
              </div>
            </PopoverContent>
          </Popover>
        )}
      </div>

      {/* Row 2: Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />

        {/* Action type */}
        <Select
          value={filters.action}
          onValueChange={(v) => updateFilter('action', v === '__all__' ? '' : v)}
        >
          <SelectTrigger className="w-[180px] h-9 text-xs">
            <SelectValue placeholder="All Actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Actions</SelectItem>
            {(actionTypes ?? []).map((action) => (
              <SelectItem key={action} value={action}>
                {action}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Category */}
        <Select
          value={filters.category}
          onValueChange={(v) => updateFilter('category', v === '__all__' ? '' : v)}
        >
          <SelectTrigger className="w-[160px] h-9 text-xs">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((option) => (
              <SelectItem
                key={option.value || '__all__'}
                value={option.value || '__all__'}
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Status */}
        <Select
          value={filters.status}
          onValueChange={(v) => updateFilter('status', v === '__all__' ? '' : v)}
        >
          <SelectTrigger className="w-[140px] h-9 text-xs">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem
                key={option.value || '__all__'}
                value={option.value || '__all__'}
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Actor email search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by email..."
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            className="h-9 w-[200px] pl-8 text-xs"
          />
        </div>

        {/* Active filter count + clear */}
        {activeFilterCount > 0 && (
          <div className="flex items-center gap-1.5">
            <Badge variant="secondary" className="text-xs">
              {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAll}
              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
              Clear all
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
