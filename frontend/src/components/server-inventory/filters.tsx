'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { Search, SlidersHorizontal, X } from 'lucide-react';

// ---------------------------------------------------------------------------
// Filter option definitions
// ---------------------------------------------------------------------------

const ENVIRONMENT_OPTIONS = [
  { value: 'dev', label: 'Dev' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
] as const;

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'provisioning', label: 'Provisioning' },
  { value: 'configuring', label: 'Configuring' },
  { value: 'validating', label: 'Validating' },
  { value: 'ready', label: 'Ready' },
  { value: 'failed', label: 'Failed' },
  { value: 'decommissioning', label: 'Decommissioning' },
  { value: 'decommissioned', label: 'Decommissioned' },
] as const;

const OS_OPTIONS = [
  { value: 'windows_2022', label: 'Windows Server 2022' },
  { value: 'windows_2019', label: 'Windows Server 2019' },
  { value: 'amazon_linux_2023', label: 'Amazon Linux 2023' },
  { value: 'ubuntu_2204', label: 'Ubuntu 22.04 LTS' },
  { value: 'rhel_9', label: 'RHEL 9' },
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FilterState {
  search: string;
  environments: string[];
  statuses: string[];
  osTypes: string[];
}

interface ServerFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
}

// ---------------------------------------------------------------------------
// Multi-select filter popover
// ---------------------------------------------------------------------------

interface MultiSelectFilterProps {
  label: string;
  options: ReadonlyArray<{ value: string; label: string }>;
  selected: string[];
  onSelectedChange: (selected: string[]) => void;
}

function MultiSelectFilter({
  label,
  options,
  selected,
  onSelectedChange,
}: MultiSelectFilterProps) {
  const toggleValue = (value: string) => {
    if (selected.includes(value)) {
      onSelectedChange(selected.filter((v) => v !== value));
    } else {
      onSelectedChange([...selected, value]);
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 border-dashed">
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          {label}
          {selected.length > 0 && (
            <>
              <Separator orientation="vertical" className="mx-2 h-4" />
              <Badge
                variant="secondary"
                className="rounded-sm px-1 font-normal"
              >
                {selected.length}
              </Badge>
            </>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <div className="p-2">
          <p className="text-sm font-medium text-muted-foreground mb-2">
            {label}
          </p>
          <div className="space-y-1">
            {options.map((option) => (
              <label
                key={option.value}
                className="flex items-center space-x-2 rounded-sm px-2 py-1.5 text-sm cursor-pointer hover:bg-accent"
              >
                <Checkbox
                  checked={selected.includes(option.value)}
                  onCheckedChange={() => toggleValue(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          {selected.length > 0 && (
            <>
              <Separator className="my-2" />
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center text-xs"
                onClick={() => onSelectedChange([])}
              >
                Clear
              </Button>
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Main filter bar
// ---------------------------------------------------------------------------

export function ServerFilters({ filters, onFiltersChange }: ServerFiltersProps) {
  const [localSearch, setLocalSearch] = useState(filters.search);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced search: updates parent after 300ms of idle typing
  const handleSearchChange = useCallback(
    (value: string) => {
      setLocalSearch(value);
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      debounceRef.current = setTimeout(() => {
        onFiltersChange({ ...filters, search: value });
      }, 300);
    },
    [filters, onFiltersChange],
  );

  // Sync localSearch when filters.search changes externally (e.g., clear all)
  useEffect(() => {
    setLocalSearch(filters.search);
  }, [filters.search]);

  // Clean up the debounce timer
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const activeFilterCount =
    filters.environments.length +
    filters.statuses.length +
    filters.osTypes.length +
    (filters.search ? 1 : 0);

  const clearAllFilters = () => {
    onFiltersChange({
      search: '',
      environments: [],
      statuses: [],
      osTypes: [],
    });
  };

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 items-center gap-2 flex-wrap">
        {/* Search input */}
        <div className="relative w-full sm:w-[300px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search servers..."
            value={localSearch}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9 h-9"
          />
          {localSearch && (
            <button
              onClick={() => handleSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Filter dropdowns */}
        <MultiSelectFilter
          label="Environment"
          options={ENVIRONMENT_OPTIONS}
          selected={filters.environments}
          onSelectedChange={(environments) =>
            onFiltersChange({ ...filters, environments })
          }
        />
        <MultiSelectFilter
          label="Status"
          options={STATUS_OPTIONS}
          selected={filters.statuses}
          onSelectedChange={(statuses) =>
            onFiltersChange({ ...filters, statuses })
          }
        />
        <MultiSelectFilter
          label="OS Type"
          options={OS_OPTIONS}
          selected={filters.osTypes}
          onSelectedChange={(osTypes) =>
            onFiltersChange({ ...filters, osTypes })
          }
        />

        {/* Clear all + active count */}
        {activeFilterCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-9 px-2"
            onClick={clearAllFilters}
          >
            Clear all
            <Badge variant="secondary" className="ml-1.5 rounded-sm px-1 font-normal">
              {activeFilterCount}
            </Badge>
          </Button>
        )}
      </div>
    </div>
  );
}
