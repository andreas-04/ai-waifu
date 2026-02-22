import { useEffect, useRef, useCallback } from "react";

export interface ScorePayload {
  focus: number;
  hydration: number;
  posture: number;
  productivity: number | null;
}

export interface LogPayload {
  module: string;
  level: "info" | "warning" | "alert";
  simple: string;
  detail: string;
  timestamp: number;
}

interface UseScoreSocketOptions {
  /** Called every time a score message arrives from the backend. */
  onScore: (scores: ScorePayload) => void;
  /** Called every time a log/notification message arrives from the backend. */
  onLog?: (log: LogPayload) => void;
  /** Called when the backend signals a new audio notification is ready to play. */
  onAudio?: () => void;
  /** When false the socket is closed and reconnect is suppressed. */
  enabled: boolean;
}

const WS_URL = "ws://localhost:8765/ws";
const RECONNECT_DELAY_MS = 3000;

/**
 * Connects to the backend WsNotifier WebSocket at ws://localhost:8765/ws.
 * Parses `{ type: "score", focus, hydration, posture }` frames and forwards
 * them to `onScore`.  Automatically reconnects with a 3-second delay on close,
 * matching the behaviour of the original dashboard.js.
 */
export function useScoreSocket({ onScore, onLog, onAudio, enabled }: UseScoreSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stable refs so the connect closure never becomes stale
  const onScoreRef = useRef(onScore);
  const onLogRef = useRef(onLog);
  const onAudioRef = useRef(onAudio);
  const enabledRef = useRef(enabled);
  onScoreRef.current = onScore;
  onLogRef.current = onLog;
  onAudioRef.current = onAudio;
  enabledRef.current = enabled;

  const cleanup = useCallback(() => {
    if (reconnectRef.current !== null) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent the reconnect branch from firing
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabledRef.current) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === "score") {
          onScoreRef.current({
            focus:        data.focus        ?? 0,
            hydration:    data.hydration    ?? 0,
            posture:      data.posture      ?? 0,
            productivity: data.productivity ?? null,
          });
        } else if (data.type === "audio") {
          onAudioRef.current?.();
        } else if (data.module && data.level && data.simple) {
          onLogRef.current?.({
            module:    data.module,
            level:     data.level,
            simple:    data.simple,
            detail:    data.detail ?? data.simple,
            timestamp: data.timestamp ?? Date.now() / 1000,
          });
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (enabledRef.current) {
        // Reconnect after delay – same 3 s logic as old dashboard.js
        reconnectRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => {
      ws.close(); // triggers onclose → schedules reconnect
    };
  }, []); // stable: only reads refs

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      cleanup();
    }
    return cleanup;
  }, [enabled, connect, cleanup]);
}
