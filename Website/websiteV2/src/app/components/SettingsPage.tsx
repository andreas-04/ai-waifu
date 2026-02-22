import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Camera, Monitor, Power, User, Briefcase, FileText, Check } from "lucide-react";

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
          <div
            style={{
              color: checked ? "#FAFAFF" : "rgba(250,250,255,0.65)",
              fontSize: 14,
              fontFamily: "'Inter', sans-serif",
              fontWeight: 500,
              marginBottom: 2,
              transition: "color 0.3s ease",
            }}
          >
            {label}
          </div>
          <div
            style={{
              color: "rgba(250,250,255,0.3)",
              fontSize: 12,
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {description}
          </div>
        </div>
      </div>

      {/* Toggle */}
      <div
        onClick={onChange}
        style={{
          width: 46,
          height: 26,
          borderRadius: 999,
          background: checked ? color : "rgba(255,255,255,0.1)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          padding: 3,
          transition: "background 0.3s ease",
          flexShrink: 0,
          boxShadow: checked ? `0 0 12px rgba(${hexToRgb(color)}, 0.4)` : "none",
          position: "relative",
        }}
        role="switch"
        aria-checked={checked}
      >
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "white",
            transform: checked ? "translateX(20px)" : "translateX(0)",
            transition: "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
          }}
        />
      </div>
    </div>
  );
}

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
    border: focused
      ? "1px solid rgba(167,139,250,0.5)"
      : "1px solid rgba(255,255,255,0.08)",
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
      {/* Icon */}
      <div
        style={{
          position: "absolute",
          left: 14,
          top: multiline ? 18 : "50%",
          transform: multiline ? "none" : "translateY(-50%)",
          color: focused ? "rgba(167,139,250,0.7)" : "rgba(250,250,255,0.25)",
          display: "flex",
          alignItems: "center",
          zIndex: 1,
          pointerEvents: "none",
          transition: "color 0.25s ease",
        }}
      >
        {icon}
      </div>

      {/* Floating label */}
      <label
        style={{
          position: "absolute",
          left: 44,
          top: raised ? 8 : multiline ? 18 : "50%",
          transform: raised || multiline ? "none" : "translateY(-50%)",
          fontSize: raised ? 10 : 14,
          fontFamily: "'Inter', sans-serif",
          fontWeight: raised ? 600 : 400,
          letterSpacing: raised ? "0.08em" : "0",
          color: focused
            ? "rgba(167,139,250,0.85)"
            : raised
            ? "rgba(250,250,255,0.35)"
            : "rgba(250,250,255,0.3)",
          textTransform: raised ? "uppercase" : "none",
          transition: "all 0.2s ease",
          pointerEvents: "none",
          zIndex: 1,
        }}
      >
        {label}
      </label>

      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          rows={3}
          style={commonStyle}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={commonStyle}
        />
      )}
    </div>
  );
}

function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return "255,255,255";
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`;
}

export function SettingsPage() {
  const [settings, setSettings] = useState({
    systemEnabled: false,
    cameraAccess: false,
    screenAccess: false,
  });
  const [profile, setProfile] = useState({
    name: "",
    jobTitle: "",
    projectDescription: "",
  });
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  // Pre-populate from Flask on mount
  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((data) => {
        setSettings({
          systemEnabled: Boolean(data.system_enabled),
          cameraAccess:  Boolean(data.camera_enabled),
          screenAccess:  Boolean(data.screen_enabled),
        });
        setProfile({
          name:               data.user_name    ?? "",
          jobTitle:           data.user_job     ?? "",
          projectDescription: data.user_project ?? "",
        });
      })
      .catch(() => {}); // Flask not running — keep blank defaults
  }, []);

  const handleSaveSettings = async () => {
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_enabled: settings.systemEnabled,
          camera_enabled: settings.cameraAccess,
          screen_enabled: settings.screenAccess,
        }),
      });
    } catch { /* ignore network errors */ }
    setSettingsSaved(true);
    setTimeout(() => setSettingsSaved(false), 2000);
  };

  const handleSaveProfile = async () => {
    try {
      await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name:         profile.name,
          job_title:    profile.jobTitle,
          project_desc: profile.projectDescription,
        }),
      });
    } catch { /* ignore network errors */ }
    setProfileSaved(true);
    setTimeout(() => setProfileSaved(false), 2000);
  };

  const cardStyle: React.CSSProperties = {
    background: "rgba(255,255,255,0.025)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 24,
    padding: "28px 28px 24px",
    backdropFilter: "blur(12px)",
    boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
  };

  const sectionTitleStyle: React.CSSProperties = {
    color: "#FAFAFF",
    fontSize: 16,
    fontFamily: "'Inter', sans-serif",
    fontWeight: 500,
    letterSpacing: "-0.02em",
    marginBottom: 4,
  };

  const sectionSubtitleStyle: React.CSSProperties = {
    color: "rgba(250,250,255,0.35)",
    fontSize: 12,
    fontFamily: "'Inter', sans-serif",
    marginBottom: 24,
  };

  return (
    <div
      style={{
        minHeight: "calc(100vh - 56px)",
        position: "relative",
        zIndex: 1,
        padding: "36px 32px 48px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 900,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* Settings card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          style={cardStyle}
        >
          <div style={sectionTitleStyle}>System Settings</div>
          <div style={sectionSubtitleStyle}>
            Configure machine vision access and session controls.
          </div>

          <div>
            <ToggleItem
              label="System Enabled"
              description="Enable the kova.ai monitoring engine"
              checked={settings.systemEnabled}
              onChange={() =>
                setSettings((s) => ({
                  ...s,
                  systemEnabled: !s.systemEnabled,
                }))
              }
              color="#22D3EE"
              icon={<Power size={15} strokeWidth={2} />}
            />
            <ToggleItem
              label="Camera Access"
              description="Allow webcam feed for posture & hydration detection"
              checked={settings.cameraAccess}
              onChange={() =>
                setSettings((s) => ({
                  ...s,
                  cameraAccess: !s.cameraAccess,
                }))
              }
              color="#A78BFA"
              icon={<Camera size={15} strokeWidth={2} />}
            />
            <div style={{ borderBottom: "none" }}>
              <ToggleItem
                label="Screen Access"
                description="Analyse on-screen activity for productivity scoring"
                checked={settings.screenAccess}
                onChange={() =>
                  setSettings((s) => ({
                    ...s,
                    screenAccess: !s.screenAccess,
                  }))
                }
                color="#60A5FA"
                icon={<Monitor size={15} strokeWidth={2} />}
              />
            </div>
          </div>

          <button
            onClick={handleSaveSettings}
            style={{
              marginTop: 24,
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 24px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              fontFamily: "'Inter', sans-serif",
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              transition: "all 0.3s ease",
              ...(settingsSaved
                ? {
                    background: "rgba(52,211,153,0.15)",
                    color: "#34D399",
                    border: "1px solid rgba(52,211,153,0.3)",
                  }
                : {
                    background: "linear-gradient(135deg, #22D3EE 0%, #60A5FA 100%)",
                    color: "#07070F",
                    boxShadow: "0 0 20px rgba(34,211,238,0.3)",
                  }),
            }}
          >
            {settingsSaved ? (
              <>
                <Check size={13} strokeWidth={3} />
                Saved
              </>
            ) : (
              "Save changes"
            )}
          </button>
        </motion.div>

        {/* Profile card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          style={cardStyle}
        >
          <div style={sectionTitleStyle}>Profile</div>
          <div style={sectionSubtitleStyle}>
            Personalise your session context and job role.
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <FloatingInput
              label="Name"
              value={profile.name}
              onChange={(v) => setProfile((p) => ({ ...p, name: v }))}
              icon={<User size={15} strokeWidth={2} />}
            />
            <FloatingInput
              label="Job Title"
              value={profile.jobTitle}
              onChange={(v) => setProfile((p) => ({ ...p, jobTitle: v }))}
              icon={<Briefcase size={15} strokeWidth={2} />}
            />
            <FloatingInput
              label="Project Description"
              value={profile.projectDescription}
              onChange={(v) =>
                setProfile((p) => ({ ...p, projectDescription: v }))
              }
              multiline
              icon={<FileText size={15} strokeWidth={2} />}
            />
          </div>

          <button
            onClick={handleSaveProfile}
            style={{
              marginTop: 24,
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 24px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              fontFamily: "'Inter', sans-serif",
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              transition: "all 0.3s ease",
              ...(profileSaved
                ? {
                    background: "rgba(52,211,153,0.15)",
                    color: "#34D399",
                    border: "1px solid rgba(52,211,153,0.3)",
                  }
                : {
                    background: "linear-gradient(135deg, #A78BFA 0%, #60A5FA 100%)",
                    color: "#07070F",
                    boxShadow: "0 0 20px rgba(167,139,250,0.3)",
                  }),
            }}
          >
            {profileSaved ? (
              <>
                <Check size={13} strokeWidth={3} />
                Saved
              </>
            ) : (
              "Save profile"
            )}
          </button>
        </motion.div>
      </div>
    </div>
  );
}
