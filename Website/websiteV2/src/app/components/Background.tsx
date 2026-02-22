import { motion } from "motion/react";

export function Background() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#060611",
        zIndex: 0,
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      {/* Cyan orb — top right */}
      <motion.div
        animate={{ scale: [1, 1.25, 1], opacity: [0.07, 0.13, 0.07] }}
        transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
        style={{
          position: "absolute",
          top: "-10%",
          right: "-5%",
          width: 560,
          height: 560,
          borderRadius: "50%",
          background: "#22D3EE",
          filter: "blur(120px)",
        }}
      />

      {/* Violet orb — bottom left */}
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.06, 0.11, 0.06] }}
        transition={{
          duration: 11,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 2,
        }}
        style={{
          position: "absolute",
          bottom: "-15%",
          left: "-8%",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "#A78BFA",
          filter: "blur(140px)",
        }}
      />

      {/* Subtle emerald pinpoint — center */}
      <motion.div
        animate={{ scale: [1, 1.4, 1], opacity: [0.04, 0.08, 0.04] }}
        transition={{
          duration: 14,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 5,
        }}
        style={{
          position: "absolute",
          top: "40%",
          left: "45%",
          width: 300,
          height: 300,
          borderRadius: "50%",
          background: "#34D399",
          filter: "blur(100px)",
        }}
      />

      {/* Subtle grid lines */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />
    </div>
  );
}
