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
}

export type SessionMethod = "multi_agent" | "exam";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  const connect = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/consultation`);

    ws.onopen = () => {
      const token = localStorage.getItem("token");
      if (token) {
        ws.send(JSON.stringify({ token }));
      }
    };

    ws.onmessage = (event) => {
      const data: WSMessage = JSON.parse(event.data);
      if (data.type === "authenticated") {
        setConnected(true);
      }
      setLastMessage(data);
      setMessages((prev) => [...prev, data]);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  const send = useCallback((data: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
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

  const sendMessage = useCallback(
    (content: string) => {
      send({ type: "student_message", content });
    },
    [send]
  );

  const endSession = useCallback(() => {
    send({ type: "end_session" });
  }, [send]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    connected,
    messages,
    lastMessage,
    connect,
    disconnect,
    startSession,
    sendMessage,
    endSession,
    clearMessages,
  };
}
