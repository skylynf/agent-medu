import { useCallback, useEffect, useRef, useState } from "react";

export interface WSMessage {
  type: string;
  content?: string;
  emotion?: string;
  hint_level?: string;
  intervention_type?: string;
  checklist?: Record<string, any>;
  completion_rate?: number;
  score?: number;
  delta?: Record<string, any>;
  /** 与会话开场白一并下发的评估快照（嵌套在 patient_response 内） */
  eval_update?: {
    checklist?: Record<string, any>;
    completion_rate?: number;
    score?: number;
  };
  session_id?: string;
  case_id?: string;
  method?: string;
  exam_mode?: boolean;
  final_score?: number;
  report?: Record<string, any>;
  // session_summary fields
  total_messages?: number;
  student_messages?: number;
  tutor_interventions_count?: number;
  duration_seconds?: number;
  critical_missed?: string[];
  strengths?: string[];
  improvements?: string[];
  // exam summary extras
  checklist_results?: Record<string, boolean>;
  holistic_scores?: Record<string, number>;
  diagnosis_given?: string | null;
  diagnosis_correct?: boolean;
  differentials_given?: string[];
  narrative_feedback?: string;
  // server hints
  recoverable?: boolean;
  ts?: number;
}

export type SessionMethod = "multi_agent" | "single_agent" | "exam";

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";

const HEARTBEAT_INTERVAL_MS = 25_000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const intentionalCloseRef = useRef(false);

  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  const stopHeartbeat = () => {
    if (heartbeatRef.current !== null) {
      window.clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  };

  const startHeartbeat = (ws: WebSocket) => {
    stopHeartbeat();
    heartbeatRef.current = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "pong" }));
        } catch {
          // ignore — onclose 会接管状态
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  };

  const connect = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
    setStatus("connecting");
    intentionalCloseRef.current = false;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/consultation`);

    ws.onopen = () => {
      setStatus("open");
      const token = localStorage.getItem("token");
      if (token) {
        ws.send(JSON.stringify({ token }));
      }
      startHeartbeat(ws);
    };

    ws.onmessage = (event) => {
      let data: WSMessage;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      // server-side keepalive: 静默忽略，不污染上层 state
      if (data.type === "ping" || data.type === "pong") {
        if (data.type === "ping") {
          try {
            ws.send(JSON.stringify({ type: "pong" }));
          } catch {
            // ignore
          }
        }
        return;
      }
      if (data.type === "authenticated") {
        setConnected(true);
      }
      setLastMessage(data);
      setMessages((prev) => [...prev, data]);
    };

    ws.onclose = () => {
      stopHeartbeat();
      setConnected(false);
      setStatus(intentionalCloseRef.current ? "closed" : "error");
    };

    ws.onerror = () => {
      stopHeartbeat();
      setConnected(false);
      setStatus("error");
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    stopHeartbeat();
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        // ignore
      }
      wsRef.current = null;
    }
    setConnected(false);
    setStatus("closed");
  }, []);

  const send = useCallback((data: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  const startSession = useCallback(
    (caseId: string, opts: { method?: SessionMethod } = {}) => {
      send({
        type: "start_session",
        case_id: caseId,
        method: opts.method || "multi_agent",
      });
    },
    [send]
  );

  const resumeSession = useCallback(
    (sessionId: string) => send({ type: "resume_session", session_id: sessionId }),
    [send]
  );

  const sendMessage = useCallback(
    (content: string) => send({ type: "student_message", content }),
    [send]
  );

  const endSession = useCallback(() => send({ type: "end_session" }), [send]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
  }, []);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      stopHeartbeat();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    connected,
    status,
    messages,
    lastMessage,
    connect,
    disconnect,
    startSession,
    resumeSession,
    sendMessage,
    endSession,
    clearMessages,
  };
}
