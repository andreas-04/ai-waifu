import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Play, Square, Brain, Zap, Droplets, Activity } from "lucide-react";
import { MetricCard } from "./MetricCard";
import { TerminalLog } from "./TerminalLog";
import { useAppContext } from "./RootLayout";
import { useScoreSocket, type LogPayload } from "../hooks/useScoreSocket";

interface Metrics {
  focus: number;
  productivity: number;
  hydration: number;
  posture: number;
}

function getStatus(metric: keyof Metrics, value: number): string {
  const thresholds: Record<keyof Metrics, string[]> = {
    focus: ["Distracted", "Drifting", "Focused", "Deep Focus", "Flow State"],
    productivity: ["Idle", "Slow", "Active", "Productive", "Peak"],
    hydration: ["Dehydrated", "Low", "Adequate", "Good", "Optimal"],
    posture: ["Poor", "Slouching", "Neutral", "Good", "Perfect"],
  };
  const labels = thresholds[metric];
  const idx = Math.min(4, Math.floor(value / 20));
  return labels[idx];
}

function formatTime(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const METRIC_CONFIG = [
  { key: "focus" as keyof Metrics, label: "Focus", color: "#22D3EE", icon: <Brain size={14} strokeWidth={2} /> },
  { key: "productivity" as keyof Metrics, label: "Productivity", color: "#A78BFA", icon: <Zap size={14} strokeWidth={2} /> },
  { key: "hydration" as keyof Metrics, label: "Hydration", color: "#60A5FA", icon: <Droplets size={14} strokeWidth={2} /> },
  { key: "posture" as keyof Metrics, label: "Posture", color: "#34D399", icon: <Activity size={14} strokeWidth={2} /> },
];

export function HomePage() {
  const { setIsRunning: setGlobalRunning } = useAppContext();
  const [isRunning, setIsRunning] = useState(false);
  const [disabledMsg, setDisabledMsg] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Metrics>({
    focus: 0,
    productivity: 0,
    hydration: 0,
    posture: 0,
  });
  const [sessionSecs, setSessionSecs] = useState(0);
  const [logs, setLogs] = useState<LogPayload[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Restore running state if the backend subprocess was already active
  useEffect(() => {
    fetch("/api/backend/status")
      .then((r) => r.json())
      .then((data: { running: boolean }) => {
        if (data.running) {
          setIsRunning(true);
          setGlobalRunning(true);
        }
      })
      .catch(() => {}); // Flask not reachable yet — stay stopped
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggle = useCallback(async () => {
    if (!isRunning) {
      // Start backend subprocess then update UI
      try {
        const res = await fetch("/api/backend/start", { method: "POST" });
        const data = await res.json();
        if (data.status === "disabled") {
          setDisabledMsg("Enable the system in Settings first.");
          setTimeout(() => setDisabledMsg(null), 3500);
          return;
        }
      } catch { /* backend unreachable */ }
      setIsRunning(true);
      setGlobalRunning(true);
      setSessionSecs(0);
      setMetrics({ focus: 0, productivity: 0, hydration: 0, posture: 0 });
    } else {
      // Stop backend subprocess then clear UI
      try {
        await fetch("/api/backend/stop", { method: "POST" });
      } catch { /* backend unreachable */ }
      setIsRunning(false);
      setGlobalRunning(false);
      setMetrics({ focus: 0, productivity: 0, hydration: 0, posture: 0 });
    }
  }, [isRunning, setGlobalRunning]);

  // Live scores from WsNotifier — productivity is the mean of the 3 backend scores
  useScoreSocket({
    enabled: isRunning,
    onScore: ({ focus, hydration, posture }) => {
      const productivity = Math.round((focus + hydration + posture) / 3);
      setMetrics({ focus, hydration, posture, productivity });
    },
    onLog: (log) => setLogs((prev) => [...prev, log]),
    onAudio: () => {
      new Audio(`/static/notification.mp3?t=${Date.now()}`).play().catch(() => {});
    },
  });

  // Session timer
  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => setSessionSecs((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  const overallScore = isRunning
    ? Math.round(
        (metrics.focus + metrics.productivity + metrics.hydration + metrics.posture) / 4
      )
    : 0;

  return (
    <div
      style={{
        minHeight: "calc(100vh - 56px)",
        position: "relative",
        zIndex: 1,
        padding: "32px 32px 40px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      {/* Control bar */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 20,
          marginBottom: 36,
        }}
      >
        {/* Start / Stop button */}
        <button
          onClick={handleToggle}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            padding: "10px 28px",
            borderRadius: 999,
            cursor: "pointer",
            fontFamily: "'Inter', sans-serif",
            fontSize: 14,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            transition: "all 0.3s ease",
            ...(isRunning
              ? {
                  background: "rgba(255,255,255,0.06)",
                  color: "rgba(250,250,255,0.7)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  boxShadow: "none",
                }
              : {
                  background: "linear-gradient(135deg, #22D3EE 0%, #A78BFA 100%)",
                  color: "#07070F",
                  border: "none",
                  boxShadow: "0 0 28px rgba(34,211,238,0.35), 0 4px 16px rgba(0,0,0,0.3)",
                }),
          }}
        >
          {isRunning ? (
            <>
              <Square size={13} strokeWidth={2.5} />
              Stop Session
            </>
          ) : (
            <>
              <Play size={13} strokeWidth={2.5} fill="currentColor" />
              Start Session
            </>
          )}
        </button>

        {/* Status + timer */}
        <AnimatePresence mode="wait">
          {isRunning ? (
            <motion.div
              key="running"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.3 }}
              style={{ display: "flex", alignItems: "center", gap: 12 }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#34D399",
                    boxShadow: "0 0 8px #34D399",
                    display: "inline-block",
                    animation: "kova-pulse 1.8s ease-in-out infinite",
                  }}
                />
                <span
                  style={{
                    color: "rgba(250,250,255,0.55)",
                    fontSize: 13,
                    fontFamily: "'Inter', sans-serif",
                  }}
                >
                  System active
                </span>
              </div>
              <span
                style={{
                  color: "rgba(250,250,255,0.3)",
                  fontSize: 12,
                  fontFamily: "'Inter', monospace",
                  letterSpacing: "0.04em",
                  background: "rgba(255,255,255,0.05)",
                  padding: "3px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255,255,255,0.07)",
                }}
              >
                {formatTime(sessionSecs)}
              </span>
            </motion.div>
          ) : (
            <motion.div
              key="stopped"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.3 }}
            >
              <span
                style={{
                  color: "rgba(250,250,255,0.25)",
                  fontSize: 13,
                  fontFamily: "'Inter', sans-serif",
                }}
              >
                Backend stopped
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Settings-disabled warning */}
        <AnimatePresence>
          {disabledMsg && (
            <motion.span
              key="disabled"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.25 }}
              style={{
                fontSize: 12,
                fontFamily: "'Inter', sans-serif",
                color: "#F87171",
                background: "rgba(248,113,113,0.08)",
                border: "1px solid rgba(248,113,113,0.2)",
                borderRadius: 8,
                padding: "4px 12px",
              }}
            >
              {disabledMsg}
            </motion.span>
          )}
        </AnimatePresence>

        {/* Overall score pill */}
        {isRunning && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              marginLeft: 4,
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 999,
              padding: "4px 14px 4px 10px",
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontFamily: "'Inter', sans-serif",
                fontWeight: 600,
                letterSpacing: "0.1em",
                color: "rgba(250,250,255,0.35)",
                textTransform: "uppercase",
              }}
            >
              Score
            </span>
            <span
              style={{
                fontSize: 16,
                fontFamily: "'Inter', sans-serif",
                fontWeight: 300,
                color: "#FAFAFF",
                letterSpacing: "-0.03em",
              }}
            >
              {overallScore}
            </span>
          </motion.div>
        )}
      </motion.div>

      {/* Metrics grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 16,
          width: "100%",
          maxWidth: 900,
        }}
      >
        {METRIC_CONFIG.map((cfg, i) => (
          <MetricCard
            key={cfg.key}
            title={cfg.label}
            value={metrics[cfg.key]}
            color={cfg.color}
            icon={cfg.icon}
            status={getStatus(cfg.key, metrics[cfg.key])}
            isRunning={isRunning}
            index={i}
          />
        ))}
      </div>

      {/* Terminal log */}
      <TerminalLog logs={logs} onClear={() => setLogs([])} />
    </div>
  );
}