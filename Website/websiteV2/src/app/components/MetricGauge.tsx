interface MetricGaugeProps {
  value: number;
  color: string;
  size?: number;
  strokeWidth?: number;
  isRunning?: boolean;
}

export function MetricGauge({
  value,
  color,
  size = 180,
  strokeWidth = 9,
  isRunning = false,
}: MetricGaugeProps) {
  const r = size / 2 - strokeWidth - 6;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;

  // 270° arc — gap at bottom center
  const arcAngle = 270;
  const arcLength = circumference * (arcAngle / 360);
  const gap = circumference - arcLength;

  const clampedValue = Math.max(0, Math.min(100, value));
  const valueDash = (clampedValue / 100) * arcLength;

  // Tick marks
  const ticks = [0, 25, 50, 75, 100];

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ overflow: "visible" }}
    >
      {/* Outer ambient glow ring — only when running and value > 0 */}
      {isRunning && clampedValue > 10 && (
        <circle
          cx={cx}
          cy={cy}
          r={r + 4}
          fill="none"
          stroke={color}
          strokeWidth={2}
          strokeDasharray={`${valueDash} ${circumference - valueDash}`}
          strokeLinecap="round"
          transform={`rotate(135, ${cx}, ${cy})`}
          style={{
            opacity: 0.15,
            filter: `blur(4px)`,
            transition: "stroke-dasharray 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      )}

      {/* Track arc */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.07)"
        strokeWidth={strokeWidth}
        strokeDasharray={`${arcLength} ${gap}`}
        strokeLinecap="round"
        transform={`rotate(135, ${cx}, ${cy})`}
      />

      {/* Value arc */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={`${valueDash} ${circumference - valueDash}`}
        strokeLinecap="round"
        transform={`rotate(135, ${cx}, ${cy})`}
        style={{
          transition: "stroke-dasharray 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          filter:
            clampedValue > 5 ? `drop-shadow(0 0 7px ${color})` : "none",
          opacity: clampedValue > 0 ? 1 : 0,
        }}
      />
    </svg>
  );
}
