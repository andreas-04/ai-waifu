import { Link, useLocation } from "react-router";
import { Settings } from "lucide-react";
import logoImg from "@/assets/fd4848081cda081057cc0e5b2d7458b5c510f960.png";

interface NavBarProps {
  isRunning: boolean;
  onSettingsOpen: () => void;
}

export function NavBar({ isRunning, onSettingsOpen }: NavBarProps) {
  const location = useLocation();
  const isHome = location.pathname === "/";

  return (
    <nav
      style={{
        background: "rgba(6, 6, 17, 0.75)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        position: "relative",
        zIndex: 50,
      }}
      className="flex items-center justify-between px-6 h-14"
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <img
          src={logoImg}
          alt="Focus Fairy"
          style={{ width: 36, height: 36, objectFit: "contain", filter: "drop-shadow(0 0 8px rgba(180, 255, 200, 0.4))" }}
        />
        <span
          style={{
            color: "#FAFAFF",
            fontFamily: "'Inter', sans-serif",
            fontSize: 15,
            fontWeight: 500,
            letterSpacing: "-0.03em",
          }}
        >
          Focus
          <span style={{ color: "rgba(52, 211, 153, 0.85)", fontWeight: 400 }}>
            {" "}Fairy
          </span>
        </span>

        {/* Live indicator */}
        {isRunning && (
          <div
            className="flex items-center gap-1.5 ml-1"
            style={{
              background: "rgba(52, 211, 153, 0.1)",
              border: "1px solid rgba(52, 211, 153, 0.2)",
              borderRadius: 999,
              padding: "3px 8px",
            }}
          >
            <span
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: "#34D399",
                display: "inline-block",
                boxShadow: "0 0 6px #34D399",
                animation: "kova-pulse 1.8s ease-in-out infinite",
              }}
            />
            <span
              style={{
                color: "#34D399",
                fontSize: 10,
                fontFamily: "'Inter', sans-serif",
                fontWeight: 600,
                letterSpacing: "0.1em",
              }}
            >
              LIVE
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Link
          to="/"
          style={{
            padding: "5px 18px",
            borderRadius: 999,
            fontSize: 13,
            fontFamily: "'Inter', sans-serif",
            fontWeight: 500,
            color: isHome ? "#FAFAFF" : "rgba(250,250,255,0.4)",
            background: isHome ? "rgba(255,255,255,0.09)" : "transparent",
            textDecoration: "none",
            transition: "all 0.25s ease",
            letterSpacing: "-0.01em",
            border: "1px solid transparent",
          }}
        >
          Home
        </Link>
        <button
          onClick={onSettingsOpen}
          title="Settings"
          style={{
            width: 34,
            height: 34,
            borderRadius: 999,
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(255,255,255,0.05)",
            color: "rgba(250,250,255,0.45)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; e.currentTarget.style.color = "#FAFAFF"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "rgba(250,250,255,0.45)"; }}
        >
          <Settings size={15} strokeWidth={1.8} />
        </button>
      </div>
    </nav>
  );
}