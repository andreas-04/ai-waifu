import { useState } from "react";
import { motion } from "motion/react";
import { MetricGauge } from "./MetricGauge";

interface MetricCardProps {
  title: string;
  value: number;
  color: string;
  icon: React.ReactNode;
  status: string;
  isRunning: boolean;
  index: number;
}

export function MetricCard({
  title,
  value,
  color,
  icon,
  status,
  isRunning,
  index,
}: MetricCardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered
          ? "rgba(255,255,255,0.05)"
          : "rgba(255,255,255,0.025)",
        border: hovered
          ? `1px solid rgba(${hexToRgb(color)}, 0.25)`
          : "1px solid rgba(255,255,255,0.07)",
        borderRadius: 24,
        padding: "28px 24px 20px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        position: "relative",
        overflow: "hidden",
        cursor: "default",
        transition: "background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease",
        boxShadow: hovered
          ? `0 8px 40px rgba(${hexToRgb(color)}, 0.1), 0 0 0 1px rgba(${hexToRgb(color)}, 0.05)`
          : "0 4px 24px rgba(0,0,0,0.25)",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Corner glow */}
      <div
        style={{
          position: "absolute",
          top: -50,
          right: -50,
          width: 150,
          height: 150,
          borderRadius: "50%",
          background: color,
          opacity: hovered ? 0.09 : 0.04,
          filter: "blur(40px)",
          transition: "opacity 0.3s ease",
          pointerEvents: "none",
        }}
      />

      {/* Header row */}
      <div
        className="w-full flex items-center gap-2.5"
        style={{ marginBottom: 8 }}
      >
        <span style={{ color, opacity: 0.85, display: "flex" }}>{icon}</span>
        <span
          style={{
            color: "rgba(250,250,255,0.45)",
            fontSize: 11,
            fontFamily: "'Inter', sans-serif",
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          {title}
        </span>

        {/* Live dot */}
        {isRunning && (
          <div
            style={{
              marginLeft: "auto",
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: color,
              boxShadow: `0 0 6px ${color}`,
              animation: "kova-pulse 2s ease-in-out infinite",
            }}
          />
        )}
      </div>

      {/* Gauge + value overlay */}
      <div style={{ position: "relative", width: 180, height: 180 }}>
        <MetricGauge
          value={value}
          color={color}
          size={180}
          strokeWidth={9}
          isRunning={isRunning}
        />

        {/* Center value */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            paddingBottom: "12%",
          }}
        >
          <motion.span
            key={Math.round(value)}
            initial={{ opacity: 0.6, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            style={{
              color: isRunning && value > 0 ? color : "rgba(250,250,255,0.6)",
              fontSize: 38,
              fontFamily: "'Inter', sans-serif",
              fontWeight: 300,
              letterSpacing: "-0.04em",
              lineHeight: 1,
              textShadow:
                isRunning && value > 0 ? `0 0 20px ${color}50` : "none",
            }}
          >
            {Math.round(value)}
          </motion.span>
          <span
            style={{
              color: "rgba(250,250,255,0.2)",
              fontSize: 11,
              fontFamily: "'Inter', sans-serif",
              marginTop: 5,
              letterSpacing: "0.02em",
            }}
          >
            / 100
          </span>
        </div>
      </div>

      {/* Status label */}
      <div className="flex items-center gap-2" style={{ marginTop: 8 }}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: isRunning && value > 0 ? color : "rgba(255,255,255,0.15)",
            boxShadow:
              isRunning && value > 0 ? `0 0 5px ${color}` : "none",
            transition: "all 0.4s ease",
          }}
        />
        <span
          style={{
            color:
              isRunning && value > 0 ? color : "rgba(250,250,255,0.25)",
            fontSize: 12,
            fontFamily: "'Inter', sans-serif",
            fontWeight: 500,
            opacity: 0.9,
            transition: "color 0.4s ease",
          }}
        >
          {isRunning && value > 0 ? status : "No signal"}
        </span>
      </div>
    </motion.div>
  );
}

// Utility: hex → "r,g,b" string for rgba()
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return "255,255,255";
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`;
}
