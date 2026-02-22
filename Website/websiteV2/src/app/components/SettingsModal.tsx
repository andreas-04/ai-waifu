import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Camera, Monitor, Power, User, Plus, Check, X, Mic } from "lucide-react";

// ── Helpers ──────────────────────────────────────────────────────────────────

function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return "255,255,255";
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`;
}

// ── ToggleItem ────────────────────────────────────────────────────────────────

interface ToggleItemProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: () => void;
  color: string;
  icon: React.ReactNode;
}

function ToggleItem({ label, description, checked, onChange, color, icon }: ToggleItemProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "16px 0",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            background: checked ? `rgba(${hexToRgb(color)}, 0.12)` : "rgba(255,255,255,0.05)",
            border: checked ? `1px solid rgba(${hexToRgb(color)}, 0.25)` : "1px solid rgba(255,255,255,0.07)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: checked ? color : "rgba(250,250,255,0.35)",
            flexShrink: 0,
            transition: "all 0.3s ease",
          }}
        >
          {icon}
        </div>
        <div>
          <div style={{ color: checked ? "#FAFAFF" : "rgba(250,250,255,0.65)", fontSize: 14, fontFamily: "'Inter', sans-serif", fontWeight: 500, marginBottom: 2, transition: "color 0.3s ease" }}>
            {label}
          </div>
          <div style={{ color: "rgba(250,250,255,0.3)", fontSize: 12, fontFamily: "'Inter', sans-serif" }}>
            {description}
          </div>
        </div>
      </div>

      <div
        onClick={onChange}
        role="switch"
        aria-checked={checked}
        style={{
          width: 46, height: 26, borderRadius: 999,
          background: checked ? color : "rgba(255,255,255,0.1)",
          cursor: "pointer", display: "flex", alignItems: "center",
          padding: 3, transition: "background 0.3s ease", flexShrink: 0,
          boxShadow: checked ? `0 0 12px rgba(${hexToRgb(color)}, 0.4)` : "none",
        }}
      >
        <div
          style={{
            width: 20, height: 20, borderRadius: "50%", background: "white",
            transform: checked ? "translateX(20px)" : "translateX(0)",
            transition: "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
          }}
        />
      </div>
    </div>
  );
}

// ── FloatingInput ─────────────────────────────────────────────────────────────

interface FloatingInputProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  icon: React.ReactNode;
}

function FloatingInput({ label, value, onChange, multiline = false, icon }: FloatingInputProps) {
  const [focused, setFocused] = useState(false);
  const raised = focused || value.length > 0;

  const commonStyle: React.CSSProperties = {
    width: "100%",
    background: "rgba(255,255,255,0.04)",
    border: focused ? "1px solid rgba(167,139,250,0.5)" : "1px solid rgba(255,255,255,0.08)",
    borderRadius: 14,
    padding: "22px 16px 10px 44px",
    color: "#FAFAFF",
    fontSize: 14,
    fontFamily: "'Inter', sans-serif",
    fontWeight: 400,
    outline: "none",
    resize: "none" as const,
    transition: "border-color 0.25s ease, box-shadow 0.25s ease",
    boxShadow: focused ? "0 0 0 3px rgba(167,139,250,0.1)" : "none",
  };

  return (
    <div style={{ position: "relative" }}>
      <div style={{ position: "absolute", left: 14, top: multiline ? 18 : "50%", transform: multiline ? "none" : "translateY(-50%)", color: focused ? "rgba(167,139,250,0.7)" : "rgba(250,250,255,0.25)", display: "flex", alignItems: "center", zIndex: 1, pointerEvents: "none", transition: "color 0.25s ease" }}>
        {icon}
      </div>
      <label
        style={{
          position: "absolute", left: 44,
          top: raised ? 8 : multiline ? 18 : "50%",
          transform: raised || multiline ? "none" : "translateY(-50%)",
          fontSize: raised ? 10 : 14,
          fontFamily: "'Inter', sans-serif",
          fontWeight: raised ? 600 : 400,
          letterSpacing: raised ? "0.08em" : "0",
          color: focused ? "rgba(167,139,250,0.85)" : raised ? "rgba(250,250,255,0.35)" : "rgba(250,250,255,0.3)",
          textTransform: raised ? "uppercase" : "none",
          transition: "all 0.2s ease",
          pointerEvents: "none", zIndex: 1,
        }}
      >
        {label}
      </label>
      {multiline ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} rows={3} style={commonStyle} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={commonStyle} />
      )}
    </div>
  );
}

// ── SettingsModal ─────────────────────────────────────────────────────────────

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [settings, setSettings] = useState({
    systemEnabled: false, cameraAccess: false, screenAccess: false,
    selectedVoice: "Voice 1",
  });
  const [profile, setProfile] = useState({ name: "" });
  const [blocklist, setBlocklist] = useState<string[]>([]);
  const [prodlist, setProdlist] = useState<string[]>([]);
  const [blocklistInput, setBlocklistInput] = useState("");
  const [prodlistInput, setProdlistInput] = useState("");
  const [saved, setSaved] = useState(false);

  // Load from Flask whenever modal opens
  useEffect(() => {
    if (!isOpen) return;
    fetch("/api/settings")
      .then((r) => r.json())
      .then((data) => {
        setSettings({
          systemEnabled:     Boolean(data.system_enabled),
          cameraAccess:      Boolean(data.camera_enabled),
          screenAccess:      Boolean(data.screen_enabled),
          selectedVoice:     data.selected_voice ?? "Voice 1",
        });
        setProfile({ name: data.user_name ?? "" });
        setBlocklist(data.blocklist ? data.blocklist.split(",").map((s: string) => s.trim()).filter(Boolean) : []);
        setProdlist(data.prodlist   ? data.prodlist.split(",").map((s: string) => s.trim()).filter(Boolean)   : []);
      })
      .catch(() => {});
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  const handleSave = async () => {
    try {
      await Promise.all([
        fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            system_enabled:     settings.systemEnabled,
            camera_enabled:     settings.cameraAccess,
            screen_enabled:     settings.screenAccess,
            selected_voice:     settings.selectedVoice,
            blocklist:          blocklist.join(","),
            prodlist:           prodlist.join(","),
          }),
        }),
        fetch("/api/profile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: profile.name }),
        }),
      ]);
    } catch { /* ignore */ }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const addBlocklist = () => {
    const t = blocklistInput.trim();
    if (!t || blocklist.includes(t)) return;
    setBlocklist((p) => [...p, t]);
    setBlocklistInput("");
  };
  const removeBlocklist = (kw: string) => setBlocklist((p) => p.filter((k) => k !== kw));

  const addProdlist = () => {
    const t = prodlistInput.trim();
    if (!t || prodlist.includes(t)) return;
    setProdlist((p) => [...p, t]);
    setProdlistInput("");
  };
  const removeProdlist = (kw: string) => setProdlist((p) => p.filter((k) => k !== kw));

  const cardStyle: React.CSSProperties = {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 20,
    padding: "24px 24px 20px",
  };

  const sectionTitleStyle: React.CSSProperties = {
    color: "#FAFAFF", fontSize: 15, fontFamily: "'Inter', sans-serif",
    fontWeight: 500, letterSpacing: "-0.02em", marginBottom: 3,
  };

  const sectionSubtitleStyle: React.CSSProperties = {
    color: "rgba(250,250,255,0.35)", fontSize: 12,
    fontFamily: "'Inter', sans-serif", marginBottom: 20,
  };

  const saveButtonStyle = (saved: boolean, gradient: string, glow: string): React.CSSProperties => ({
    marginTop: 20,
    display: "flex", alignItems: "center", gap: 8,
    padding: "9px 22px", borderRadius: 999,
    cursor: "pointer", fontFamily: "'Inter', sans-serif",
    fontSize: 13, fontWeight: 600, letterSpacing: "-0.01em",
    transition: "all 0.3s ease",
    ...(saved
      ? { background: "rgba(52,211,153,0.15)", color: "#34D399", border: "1px solid rgba(52,211,153,0.3)" }
      : { background: gradient, color: "#07070F", border: "none", boxShadow: glow }),
  });

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: "fixed", inset: 0, zIndex: 100,
              background: "rgba(4,4,14,0.75)",
              backdropFilter: "blur(8px)",
              WebkitBackdropFilter: "blur(8px)",
            }}
          />

          {/* Centering container — flex keeps the panel truly centered
              without conflicting with Framer Motion's y transform */}
          <div
            style={{
              position: "fixed", inset: 0, zIndex: 101,
              display: "flex", alignItems: "center", justifyContent: "center",
              pointerEvents: "none",
            }}
          >
          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            style={{
              pointerEvents: "auto",
              width: "min(900px, calc(100vw - 48px))",
              maxHeight: "calc(100vh - 80px)",
              overflowY: "auto",
              background: "rgba(10,10,24,0.92)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: 28,
              padding: "28px 28px 32px",
              boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <div>
                <div style={{ color: "#FAFAFF", fontSize: 18, fontFamily: "'Inter', sans-serif", fontWeight: 500, letterSpacing: "-0.03em" }}>
                  Settings
                </div>
                <div style={{ color: "rgba(250,250,255,0.3)", fontSize: 12, fontFamily: "'Inter', sans-serif", marginTop: 2 }}>
                  System configuration and profile
                </div>
              </div>
              <button
                onClick={onClose}
                style={{
                  width: 32, height: 32, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(255,255,255,0.05)", color: "rgba(250,250,255,0.5)",
                  cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; e.currentTarget.style.color = "#FAFAFF"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "rgba(250,250,255,0.5)"; }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>

            {/* Two-column layout */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
              {/* System Settings */}
              <div style={cardStyle}>
                <div style={sectionTitleStyle}>System Settings</div>
                <div style={sectionSubtitleStyle}>Configure machine vision access and session controls.</div>
                <div>
                  <ToggleItem label="System Enabled" description="Enable the AI monitoring engine" checked={settings.systemEnabled} onChange={() => setSettings((s) => ({ ...s, systemEnabled: !s.systemEnabled }))} color="#22D3EE" icon={<Power size={15} strokeWidth={2} />} />
                  <ToggleItem label="Camera Access" description="Allow webcam feed for posture & hydration detection" checked={settings.cameraAccess} onChange={() => setSettings((s) => ({ ...s, cameraAccess: !s.cameraAccess }))} color="#A78BFA" icon={<Camera size={15} strokeWidth={2} />} />
                  <ToggleItem label="Screen Access" description="Analyse on-screen activity for productivity scoring" checked={settings.screenAccess} onChange={() => setSettings((s) => ({ ...s, screenAccess: !s.screenAccess }))} color="#60A5FA" icon={<Monitor size={15} strokeWidth={2} />} />
                </div>

                {/* Voice selection */}
                <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                  <div style={{ fontSize: 11, fontFamily: "'Inter', sans-serif", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(250,250,255,0.3)", marginBottom: 12 }}>AI Voice</div>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <Mic size={15} strokeWidth={2} style={{ position: "absolute", left: 12, color: "rgba(250,250,255,0.3)", pointerEvents: "none" }} />
                    <select
                      value={settings.selectedVoice}
                      onChange={(e) => setSettings((s) => ({ ...s, selectedVoice: e.target.value }))}
                      style={{
                        width: "100%", appearance: "none",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 12, padding: "10px 14px 10px 38px",
                        color: "#FAFAFF", fontSize: 13, fontFamily: "'Inter', sans-serif",
                        outline: "none", cursor: "pointer",
                      }}
                    >
                      {["Voice 1", "Voice 2", "Voice 3", "Voice 4"].map((v) => (
                        <option key={v} value={v} style={{ background: "#0a0a18" }}>{v}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Profile */}
              <div style={cardStyle}>
                <div style={sectionTitleStyle}>Profile</div>
                <div style={sectionSubtitleStyle}>Your name and content lists for scoring context.</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <FloatingInput label="Name" value={profile.name} onChange={(v) => setProfile((p) => ({ ...p, name: v }))} icon={<User size={15} strokeWidth={2} />} />

                  {/* Blocklist */}
                  {(() => {
                    const listSection = (label: string, sublabel: string, items: string[], input: string, setInput: (v: string) => void, add: () => void, remove: (v: string) => void, accentColor: string) => (
                      <div>
                        <div style={{ fontSize: 11, fontFamily: "'Inter', sans-serif", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(250,250,255,0.35)", marginBottom: 4 }}>{label}</div>
                        <div style={{ fontSize: 11, fontFamily: "'Inter', sans-serif", color: "rgba(250,250,255,0.25)", marginBottom: 8 }}>{sublabel}</div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <input
                            type="text" value={input} placeholder="Add entry…"
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
                            style={{ flex: 1, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "9px 14px", color: "#FAFAFF", fontSize: 13, fontFamily: "'Inter', sans-serif", outline: "none" }}
                            onFocus={(e) => { e.currentTarget.style.borderColor = `rgba(${hexToRgb(accentColor)},0.5)`; }}
                            onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; }}
                          />
                          <button onClick={add} style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: `rgba(${hexToRgb(accentColor)},0.12)`, border: `1px solid rgba(${hexToRgb(accentColor)},0.25)`, color: accentColor, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s ease" }}>
                            <Plus size={16} strokeWidth={2.5} />
                          </button>
                        </div>
                        {items.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                            {items.map((kw) => (
                              <div key={kw} style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 10px 3px 12px", borderRadius: 999, border: `1px solid rgba(${hexToRgb(accentColor)},0.3)`, background: `rgba(${hexToRgb(accentColor)},0.07)`, color: "rgba(250,250,255,0.75)", fontSize: 12, fontFamily: "'Inter', sans-serif" }}>
                                <span>{kw}</span>
                                <button onClick={() => remove(kw)} style={{ display: "flex", alignItems: "center", background: "none", border: "none", cursor: "pointer", padding: 0, color: "rgba(250,250,255,0.3)", transition: "color 0.15s" }} onMouseEnter={(e) => { e.currentTarget.style.color = "#F87171"; }} onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(250,250,255,0.3)"; }}>
                                  <X size={11} strokeWidth={2.5} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                    return (
                      <>
                        {listSection("Blocklist", "Sites/apps that count against your focus score.", blocklist, blocklistInput, setBlocklistInput, addBlocklist, removeBlocklist, "#F87171")}
                        {listSection("Prodlist", "Sites/apps that boost your productivity score.", prodlist, prodlistInput, setProdlistInput, addProdlist, removeProdlist, "#34D399")}
                      </>
                    );
                  })()}
                </div>
              </div>
            </div>

            {/* Single save button */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
              <button
                onClick={handleSave}
                style={saveButtonStyle(saved, "linear-gradient(135deg, #22D3EE 0%, #A78BFA 100%)", "0 0 20px rgba(34,211,238,0.3), 0 0 40px rgba(167,139,250,0.2)")}
              >
                {saved ? <><Check size={13} strokeWidth={3} />Saved</> : "Save changes"}
              </button>
            </div>
          </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
