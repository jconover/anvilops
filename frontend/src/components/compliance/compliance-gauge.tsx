'use client';

import { useEffect, useState } from 'react';

interface ComplianceGaugeProps {
  percentage: number;
  size?: number;
}

function getGaugeColor(percentage: number): string {
  if (percentage >= 90) return '#22c55e'; // green-500
  if (percentage >= 70) return '#eab308'; // yellow-500
  return '#ef4444'; // red-500
}

function getGaugeTrailColor(percentage: number): string {
  if (percentage >= 90) return '#dcfce7'; // green-100
  if (percentage >= 70) return '#fef9c3'; // yellow-100
  return '#fee2e2'; // red-100
}

function getGaugeLabel(percentage: number): string {
  if (percentage >= 95) return 'Excellent';
  if (percentage >= 90) return 'Good';
  if (percentage >= 70) return 'Attention Needed';
  return 'Critical';
}

export function ComplianceGauge({ percentage, size = 200 }: ComplianceGaugeProps) {
  const [animatedPercentage, setAnimatedPercentage] = useState(0);

  useEffect(() => {
    // Animate from 0 to the target percentage
    const timer = setTimeout(() => {
      setAnimatedPercentage(percentage);
    }, 100);
    return () => clearTimeout(timer);
  }, [percentage]);

  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedPercentage / 100) * circumference;
  const center = size / 2;
  const color = getGaugeColor(percentage);
  const trailColor = getGaugeTrailColor(percentage);
  const label = getGaugeLabel(percentage);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
        >
          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={trailColor}
            strokeWidth={strokeWidth}
            className="dark:opacity-30"
          />
          {/* Progress arc */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-[stroke-dashoffset] duration-1000 ease-out"
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-4xl font-bold tabular-nums"
            style={{ color }}
          >
            {Math.round(animatedPercentage)}%
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            {label}
          </span>
        </div>
      </div>
      <p className="text-sm font-medium text-muted-foreground">
        Fleet Compliance
      </p>
    </div>
  );
}
