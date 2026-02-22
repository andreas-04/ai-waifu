import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, ChevronUp, Terminal, Trash2 } from "lucide-react";
import type { LogPayload } from "../hooks/useScoreSocket";

interface TerminalLogProps {
  logs: LogPayload[];
  onClear: () => void;
}

const MODULE_COLORS: Record<string, string> = {
  posture:   "#34D399",
  hydration: "#60A5FA",
  focus:     "#22D3EE",
};

const LEVEL_COLORS: Record<string, string> = {
  info:    "rgba(250,250,255,0.45)",
  warning: "#FBBF24",
  alert:   "#F87171",
};

const LEVEL_BADGE_BG: Record<string, string> = {
  info:    "rgba(255,255,255,0.06)",
  warning: "rgba(251,191,36,0.12)",
  alert:   "rgba(248,113,113,0.12)",
};

function formatTs(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export function TerminalLog({ logs, onClear }: TerminalLogProps) {
  const [isOpen, setIsOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wasAtBottomRef = useRef(true);

  // Track whether user is scrolled to bottom before new logs arrive
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    wasAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  // Auto-scroll only when already at bottom
  useEffect(() => {
    if (wasAtBottomRef.current && isOpen) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, isOpen]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      style={{
        width: "100%",
        maxWidth: 900,
        marginTop: 20,
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(7,7,15,0.65)",
        backdropFilter: "blur(12px)",
        overflow: "hidden",
      }}
    >
      {/* ── Header ── */}
      <div
        onClick={() => setIsOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 16px",
          cursor: "pointer",
          userSelect: "none",
          borderBottom: isOpen ? "1px solid rgba(255,255,255,0.06)" : "none",
          transition: "border-bottom 0.2s",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Terminal size={14} color="rgba(250,250,255,0.4)" strokeWidth={2} />
          <span
            style={{
              fontFamily: "'Inter', monospace",
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "rgba(250,250,255,0.4)",
            }}
          >
            System Log
          </span>
          {logs.length > 0 && (
            <span
              style={{
                fontSize: 10,
                fontFamily: "'Inter', monospace",
                color: "rgba(250,250,255,0.25)",
                background: "rgba(255,255,255,0.06)",
                borderRadius: 4,
                padding: "1px 7px",
                marginLeft: 2,
              }}
            >
              {logs.length}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Clear button — only shown when open and there are logs */}
          <AnimatePresence>
            {isOpen && logs.length > 0 && (
              <motion.button
                key="clear"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.18 }}
                onClick={(e) => {
                  e.stopPropagation();
                  onClear();
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "rgba(250,250,255,0.3)",
                  fontFamily: "'Inter', sans-serif",
                  fontSize: 11,
                  padding: "2px 6px",
                  borderRadius: 6,
                  transition: "color 0.2s",
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.color = "rgba(248,113,113,0.8)")
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.color = "rgba(250,250,255,0.3)")
                }
              >
                <Trash2 size={12} strokeWidth={2} />
                Clear
              </motion.button>
            )}
          </AnimatePresence>

          {isOpen ? (
            <ChevronUp size={14} color="rgba(250,250,255,0.3)" strokeWidth={2} />
          ) : (
            <ChevronDown size={14} color="rgba(250,250,255,0.3)" strokeWidth={2} />
          )}
        </div>
      </div>

      {/* ── Body ── */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div
              ref={containerRef}
              onScroll={handleScroll}
              style={{
                height: 220,
                overflowY: "auto",
                padding: "10px 0",
                scrollbarWidth: "thin",
                scrollbarColor: "rgba(255,255,255,0.1) transparent",
              }}
            >
              {logs.length === 0 ? (
                <div
                  style={{
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "rgba(250,250,255,0.15)",
                    fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
                    fontSize: 12,
                  }}
                >
                  Waiting for messages…
                </div>
              ) : (
                logs.map((log, i) => (
                  <LogRow key={i} log={log} />
                ))
              )}
              <div ref={bottomRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function LogRow({ log }: { log: LogPayload }) {
  const moduleColor = MODULE_COLORS[log.module] ?? "rgba(250,250,255,0.4)";
  const levelColor  = LEVEL_COLORS[log.level]   ?? LEVEL_COLORS.info;
  const levelBg     = LEVEL_BADGE_BG[log.level] ?? LEVEL_BADGE_BG.info;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 10,
        padding: "3px 16px",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
        fontSize: 12,
        lineHeight: 1.6,
        transition: "background 0.15s",
      }}
      onMouseEnter={(e) =>
        ((e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)")
      }
      onMouseLeave={(e) =>
        ((e.currentTarget as HTMLDivElement).style.background = "transparent")
      }
    >
      {/* Timestamp */}
      <span
        style={{
          flexShrink: 0,
          color: "rgba(250,250,255,0.2)",
          fontSize: 11,
          letterSpacing: "0.03em",
          minWidth: 56,
        }}
      >
        {formatTs(log.timestamp)}
      </span>

      {/* Module badge */}
      <span
        style={{
          flexShrink: 0,
          color: moduleColor,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          minWidth: 62,
        }}
      >
        {log.module}
      </span>

      {/* Level badge */}
      <span
        style={{
          flexShrink: 0,
          color: levelColor,
          background: levelBg,
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          borderRadius: 4,
          padding: "0 5px",
          minWidth: 48,
          textAlign: "center",
        }}
      >
        {log.level}
      </span>

      {/* Message */}
      <span
        style={{
          color: levelColor,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {log.detail}
      </span>
    </div>
  );
}
