'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { TrendDataPoint } from '@/lib/api/drift';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SEVERITY_COLORS = {
  critical: '#ef4444', // red-500
  high: '#f97316',     // orange-500
  medium: '#eab308',   // yellow-500
  low: '#94a3b8',      // slate-400
} as const;

const CHART_PADDING = { top: 20, right: 12, bottom: 32, left: 40 };

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DriftTrendChartProps {
  data: TrendDataPoint[];
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  point: TrendDataPoint | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DriftTrendChart({ data }: DriftTrendChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  });

  // Chart dimensions — we use a viewBox so the SVG scales responsively
  const viewWidth = 800;
  const viewHeight = 240;
  const chartWidth = viewWidth - CHART_PADDING.left - CHART_PADDING.right;
  const chartHeight = viewHeight - CHART_PADDING.top - CHART_PADDING.bottom;

  // Derive max value for the Y axis
  const maxCount = useMemo(() => {
    if (data.length === 0) return 10;
    const max = Math.max(...data.map((d) => d.count));
    // Round up to a nice number so gridlines look clean
    return Math.max(4, Math.ceil(max * 1.15));
  }, [data]);

  // Y-axis tick values
  const yTicks = useMemo(() => {
    const tickCount = 4;
    const step = maxCount / tickCount;
    return Array.from({ length: tickCount + 1 }, (_, i) => Math.round(i * step));
  }, [maxCount]);

  // Bar width and gap
  const barCount = data.length || 1;
  const gap = Math.max(1, chartWidth / barCount * 0.2);
  const barWidth = Math.max(2, (chartWidth - gap * barCount) / barCount);

  // Scales
  const xScale = useCallback(
    (index: number) =>
      CHART_PADDING.left + gap / 2 + index * (barWidth + gap),
    [barWidth, gap],
  );

  const yScale = useCallback(
    (value: number) =>
      CHART_PADDING.top + chartHeight - (value / maxCount) * chartHeight,
    [chartHeight, maxCount],
  );

  // Mouse handlers for tooltip
  function handleBarEnter(
    e: React.MouseEvent<SVGRectElement>,
    point: TrendDataPoint,
    barX: number,
  ) {
    const svg = svgRef.current;
    if (!svg) return;
    setTooltip({
      visible: true,
      x: barX + barWidth / 2,
      y: CHART_PADDING.top - 4,
      point,
    });
  }

  function handleBarLeave() {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }

  // Format date label for x-axis
  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // Determine which x-axis labels to show (avoid overlap)
  const labelInterval = Math.max(1, Math.ceil(data.length / 10));

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Drift Trend (30 Days)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            No trend data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Drift Trend (30 Days)</CardTitle>
          {/* Legend */}
          <div className="flex items-center gap-3">
            {Object.entries(SEVERITY_COLORS).map(([severity, color]) => (
              <div key={severity} className="flex items-center gap-1">
                <div
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: color }}
                />
                <span className="text-[11px] capitalize text-muted-foreground">
                  {severity}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pb-4">
        <div className="relative w-full">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${viewWidth} ${viewHeight}`}
            className="w-full"
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Gridlines */}
            {yTicks.map((tick) => (
              <g key={tick}>
                <line
                  x1={CHART_PADDING.left}
                  y1={yScale(tick)}
                  x2={viewWidth - CHART_PADDING.right}
                  y2={yScale(tick)}
                  stroke="currentColor"
                  strokeOpacity={0.08}
                  strokeWidth={1}
                />
                <text
                  x={CHART_PADDING.left - 8}
                  y={yScale(tick)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="fill-muted-foreground"
                  fontSize={10}
                >
                  {tick}
                </text>
              </g>
            ))}

            {/* Stacked bars */}
            {data.map((point, index) => {
              const x = xScale(index);
              const severities = [
                { key: 'low', value: point.low },
                { key: 'medium', value: point.medium },
                { key: 'high', value: point.high },
                { key: 'critical', value: point.critical },
              ] as const;

              let currentY = yScale(0);
              const segments: {
                key: string;
                y: number;
                height: number;
                color: string;
              }[] = [];

              for (const sev of severities) {
                if (sev.value === 0) continue;
                const segmentHeight = (sev.value / maxCount) * chartHeight;
                currentY -= segmentHeight;
                segments.push({
                  key: sev.key,
                  y: currentY,
                  height: segmentHeight,
                  color: SEVERITY_COLORS[sev.key],
                });
              }

              return (
                <g key={point.date}>
                  {/* Stacked segments */}
                  {segments.map((seg) => (
                    <rect
                      key={`${point.date}-${seg.key}`}
                      x={x}
                      y={seg.y}
                      width={barWidth}
                      height={Math.max(0, seg.height)}
                      fill={seg.color}
                      rx={1}
                      opacity={0.85}
                    />
                  ))}
                  {/* Invisible hit area for hover */}
                  <rect
                    x={x}
                    y={CHART_PADDING.top}
                    width={barWidth}
                    height={chartHeight}
                    fill="transparent"
                    onMouseEnter={(e) => handleBarEnter(e, point, x)}
                    onMouseLeave={handleBarLeave}
                    className="cursor-pointer"
                  />
                  {/* X-axis labels */}
                  {index % labelInterval === 0 && (
                    <text
                      x={x + barWidth / 2}
                      y={viewHeight - 6}
                      textAnchor="middle"
                      className="fill-muted-foreground"
                      fontSize={9}
                    >
                      {formatDate(point.date)}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Axis lines */}
            <line
              x1={CHART_PADDING.left}
              y1={yScale(0)}
              x2={viewWidth - CHART_PADDING.right}
              y2={yScale(0)}
              stroke="currentColor"
              strokeOpacity={0.15}
              strokeWidth={1}
            />
          </svg>

          {/* Tooltip overlay */}
          {tooltip.visible && tooltip.point && (
            <div
              className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg"
              style={{
                left: `${(tooltip.x / viewWidth) * 100}%`,
                top: '0px',
              }}
            >
              <p className="mb-1 font-medium">
                {formatDate(tooltip.point.date)}
              </p>
              <p className="tabular-nums">
                Total: <span className="font-semibold">{tooltip.point.count}</span>
              </p>
              <div className="mt-1 space-y-0.5">
                {tooltip.point.critical > 0 && (
                  <p className="flex items-center gap-1.5 tabular-nums">
                    <span
                      className="inline-block h-2 w-2 rounded-sm"
                      style={{ backgroundColor: SEVERITY_COLORS.critical }}
                    />
                    Critical: {tooltip.point.critical}
                  </p>
                )}
                {tooltip.point.high > 0 && (
                  <p className="flex items-center gap-1.5 tabular-nums">
                    <span
                      className="inline-block h-2 w-2 rounded-sm"
                      style={{ backgroundColor: SEVERITY_COLORS.high }}
                    />
                    High: {tooltip.point.high}
                  </p>
                )}
                {tooltip.point.medium > 0 && (
                  <p className="flex items-center gap-1.5 tabular-nums">
                    <span
                      className="inline-block h-2 w-2 rounded-sm"
                      style={{ backgroundColor: SEVERITY_COLORS.medium }}
                    />
                    Medium: {tooltip.point.medium}
                  </p>
                )}
                {tooltip.point.low > 0 && (
                  <p className="flex items-center gap-1.5 tabular-nums">
                    <span
                      className="inline-block h-2 w-2 rounded-sm"
                      style={{ backgroundColor: SEVERITY_COLORS.low }}
                    />
                    Low: {tooltip.point.low}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
