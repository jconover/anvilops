"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Check, Copy } from "lucide-react";

interface LogViewerProps {
  content: string;
  maxHeight?: string;
  className?: string;
}

/**
 * Terminal-style log output viewer with line numbers, syntax highlighting,
 * auto-scroll, and a copy button.
 */
export function LogViewer({
  content,
  maxHeight = "24rem",
  className,
}: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);

  const lines = content ? content.split("\n") : [];

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (shouldAutoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [content, shouldAutoScroll]);

  // Detect if user has scrolled away from bottom
  function handleScroll() {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 40;
    setShouldAutoScroll(isAtBottom);
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: do nothing if clipboard API is unavailable
    }
  }

  /**
   * Colorize a single log line based on common patterns:
   *   - Lines containing ERROR / FATAL / FAILED -> red
   *   - Lines containing WARN / WARNING       -> yellow
   *   - Lines containing SUCCESS / OK / COMPLETE / CREATED -> green
   *   - Timestamps at start of line            -> dimmed
   */
  function highlightLine(line: string): React.ReactNode {
    if (!line) return " "; // preserve empty lines in the DOM

    // Error patterns
    if (/\b(ERROR|FATAL|FAILED|FAILURE|error|fatal|failed)\b/.test(line)) {
      return <span className="text-red-400">{line}</span>;
    }
    // Warning patterns
    if (/\b(WARN|WARNING|warn|warning)\b/.test(line)) {
      return <span className="text-yellow-400">{line}</span>;
    }
    // Success patterns
    if (
      /\b(SUCCESS|COMPLETE|COMPLETED|CREATED|OK|PASSED|success|complete|created)\b/.test(
        line
      )
    ) {
      return <span className="text-green-400">{line}</span>;
    }
    // Info / change patterns
    if (/\b(CHANGED|changed|APPLIED|applied)\b/.test(line)) {
      return <span className="text-blue-400">{line}</span>;
    }

    return <span className="text-zinc-300">{line}</span>;
  }

  if (lines.length === 0) {
    return (
      <div
        className={cn(
          "rounded-md bg-zinc-950 p-4 text-sm text-zinc-500 font-mono",
          className
        )}
      >
        No log output available.
      </div>
    );
  }

  const gutterWidth = String(lines.length).length;

  return (
    <div className={cn("relative group", className)}>
      {/* Copy button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleCopy}
        className="absolute right-2 top-2 z-10 h-8 gap-1.5 bg-zinc-800/80 text-zinc-400 opacity-0 backdrop-blur transition-opacity hover:bg-zinc-700 hover:text-zinc-200 group-hover:opacity-100"
      >
        {copied ? (
          <>
            <Check className="h-3.5 w-3.5" />
            Copied
          </>
        ) : (
          <>
            <Copy className="h-3.5 w-3.5" />
            Copy
          </>
        )}
      </Button>

      {/* Log output */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="overflow-auto rounded-md bg-zinc-950 p-4 font-mono text-xs leading-5"
        style={{ maxHeight }}
      >
        <table className="border-collapse">
          <tbody>
            {lines.map((line, index) => (
              <tr key={index} className="hover:bg-zinc-900/50">
                {/* Line number gutter */}
                <td
                  className="select-none pr-4 text-right align-top text-zinc-600"
                  style={{ minWidth: `${gutterWidth + 1}ch` }}
                >
                  {index + 1}
                </td>
                {/* Line content */}
                <td className="whitespace-pre-wrap break-all">
                  {highlightLine(line)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
