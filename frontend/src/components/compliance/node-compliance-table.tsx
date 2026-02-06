'use client';

import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  ChevronRight,
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import type { ComplianceNode } from '@/lib/api/types';
import { DriftReport } from './drift-report';

interface NodeComplianceTableProps {
  nodes: ComplianceNode[];
  statusFilter: string;
}

type SortField = 'server_name' | 'certname' | 'status' | 'os_type' | 'puppet_role' | 'report_timestamp';
type SortDirection = 'asc' | 'desc';

function getStatusBadgeVariant(status: string): 'success' | 'warning' | 'destructive' | 'secondary' {
  switch (status.toLowerCase()) {
    case 'compliant':
    case 'unchanged':
      return 'success';
    case 'changed':
      return 'warning';
    case 'failed':
      return 'destructive';
    case 'unresponsive':
    default:
      return 'secondary';
  }
}

function getStatusLabel(status: string): string {
  switch (status.toLowerCase()) {
    case 'unchanged':
      return 'Compliant';
    default:
      return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
  }
}

function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return 'Never';

  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return then.toLocaleDateString();
}

function SortIcon({ field, sortField, sortDirection }: {
  field: SortField;
  sortField: SortField;
  sortDirection: SortDirection;
}) {
  if (field !== sortField) {
    return <ChevronsUpDown className="ml-1 inline h-3.5 w-3.5 text-muted-foreground/50" />;
  }
  return sortDirection === 'asc' ? (
    <ChevronUp className="ml-1 inline h-3.5 w-3.5" />
  ) : (
    <ChevronDown className="ml-1 inline h-3.5 w-3.5" />
  );
}

export function NodeComplianceTable({ nodes, statusFilter }: NodeComplianceTableProps) {
  const [sortField, setSortField] = useState<SortField>('server_name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [expandedNode, setExpandedNode] = useState<string | null>(null);

  const filteredNodes = useMemo(() => {
    if (statusFilter === 'all') return nodes;
    return nodes.filter((node) => {
      const normalizedStatus = node.status.toLowerCase() === 'unchanged' ? 'compliant' : node.status.toLowerCase();
      return normalizedStatus === statusFilter.toLowerCase();
    });
  }, [nodes, statusFilter]);

  const sortedNodes = useMemo(() => {
    const sorted = [...filteredNodes].sort((a, b) => {
      let aVal: string;
      let bVal: string;

      switch (sortField) {
        case 'server_name':
          aVal = a.server_name || a.certname;
          bVal = b.server_name || b.certname;
          break;
        case 'certname':
          aVal = a.certname;
          bVal = b.certname;
          break;
        case 'status':
          aVal = a.status;
          bVal = b.status;
          break;
        case 'os_type':
          aVal = a.os_type || '';
          bVal = b.os_type || '';
          break;
        case 'puppet_role':
          aVal = a.puppet_role || '';
          bVal = b.puppet_role || '';
          break;
        case 'report_timestamp':
          aVal = a.report_timestamp || '';
          bVal = b.report_timestamp || '';
          break;
        default:
          return 0;
      }

      const cmp = aVal.localeCompare(bVal);
      return sortDirection === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [filteredNodes, sortField, sortDirection]);

  function handleSort(field: SortField) {
    if (field === sortField) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  }

  function handleRowClick(node: ComplianceNode) {
    const key = node.server_id || node.certname;
    setExpandedNode((prev) => (prev === key ? null : key));
  }

  if (sortedNodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
        <p className="text-sm text-muted-foreground">
          No nodes match the current filter.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8" />
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('server_name')}
          >
            Server Name
            <SortIcon field="server_name" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('certname')}
          >
            Certname
            <SortIcon field="certname" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('status')}
          >
            Status
            <SortIcon field="status" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('os_type')}
          >
            OS Type
            <SortIcon field="os_type" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('puppet_role')}
          >
            Puppet Role
            <SortIcon field="puppet_role" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
          <TableHead
            className="cursor-pointer select-none"
            onClick={() => handleSort('report_timestamp')}
          >
            Last Report
            <SortIcon field="report_timestamp" sortField={sortField} sortDirection={sortDirection} />
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedNodes.map((node) => {
          const key = node.server_id || node.certname;
          const isExpanded = expandedNode === key;

          return (
            <NodeRow
              key={key}
              node={node}
              isExpanded={isExpanded}
              onClick={() => handleRowClick(node)}
            />
          );
        })}
      </TableBody>
    </Table>
  );
}

function NodeRow({
  node,
  isExpanded,
  onClick,
}: {
  node: ComplianceNode;
  isExpanded: boolean;
  onClick: () => void;
}) {
  return (
    <>
      <TableRow
        className="cursor-pointer"
        onClick={onClick}
      >
        <TableCell className="w-8 pr-0">
          <ChevronRight
            className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
              isExpanded ? 'rotate-90' : ''
            }`}
          />
        </TableCell>
        <TableCell className="font-medium">
          {node.server_name || '--'}
        </TableCell>
        <TableCell className="font-mono text-xs">
          {node.certname}
        </TableCell>
        <TableCell>
          <Badge variant={getStatusBadgeVariant(node.status)}>
            {getStatusLabel(node.status)}
          </Badge>
        </TableCell>
        <TableCell>{node.os_type || '--'}</TableCell>
        <TableCell>
          <span className="font-mono text-xs">{node.puppet_role || '--'}</span>
        </TableCell>
        <TableCell className="text-muted-foreground">
          {formatRelativeTime(node.report_timestamp)}
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/30 p-0">
            <div className="p-4">
              <DriftReport serverId={node.server_id} certname={node.certname} />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
