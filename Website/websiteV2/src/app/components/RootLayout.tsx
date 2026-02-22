import { Outlet, useOutletContext } from "react-router";
import { useState } from "react";
import { Background } from "./Background";
import { NavBar } from "./NavBar";
import { SettingsModal } from "./SettingsModal";

interface AppContext {
  isRunning: boolean;
  setIsRunning: (v: boolean) => void;
}

export function useAppContext() {
  return useOutletContext<AppContext>();
}

export function RootLayout() {
  const [isRunning, setIsRunning] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <div
      style={{
        minHeight: "100vh",
        position: "relative",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* Animated ambient background */}
      <Background />

      {/* App shell */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <NavBar isRunning={isRunning} onSettingsOpen={() => setIsSettingsOpen(true)} />
        <Outlet context={{ isRunning, setIsRunning } satisfies AppContext} />
      </div>

      {/* Settings modal */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />

      {/* Global keyframe styles */}
      <style>{`
        @keyframes kova-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.85); }
        }

        * {
          box-sizing: border-box;
        }

        ::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        ::-webkit-scrollbar-track {
          background: rgba(255,255,255,0.03);
        }
        ::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 999px;
        }
        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.18);
        }
      `}</style>
    </div>
  );
}
