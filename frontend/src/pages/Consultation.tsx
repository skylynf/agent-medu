import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useWebSocket, WSMessage } from "../hooks/useWebSocket";
import { api, UserResponse } from "../services/api";
import ChatPanel, { ChatMessage } from "../components/ChatPanel";
import EvalSidebar from "../components/EvalSidebar";
import TutorHint from "../components/TutorHint";
import Timer from "../components/Timer";

interface Props {
  user: UserResponse;
}

export default function Consultation({ user }: Props) {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const ws = useWebSocket();

  const [caseInfo, setCaseInfo] = useState<any | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [checklist, setChecklist] = useState<Record<string, any> | null>(null);
  const [completionRate, setCompletionRate] = useState(0);
  const [score, setScore] = useState(0);
  const [tutorHint, setTutorHint] = useState<{
    content: string;
    level: string;
  } | null>(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [summary, setSummary] = useState<WSMessage | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  /** 已处理的 WS 事件条数（messages 保留全量，避免 lastMessage 被批量更新覆盖丢失） */
  const wsEventsProcessed = useRef(0);

  const applyEvalPayload = useCallback((msg: WSMessage) => {
    if (msg.checklist) setChecklist(msg.checklist);
    if (msg.completion_rate !== undefined) setCompletionRate(msg.completion_rate);
    if (msg.score !== undefined) setScore(msg.score);
  }, []);

  useEffect(() => {
    if (caseId) {
      api.cases.get(caseId).then(setCaseInfo).catch(console.error);
    }
  }, [caseId]);

  useEffect(() => {
    ws.connect();
    return () => ws.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (ws.connected && caseId && !sessionActive && !sessionEnded) {
      ws.startSession(caseId);
    }
  }, [ws.connected, caseId, sessionActive, sessionEnded]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const msgs = ws.messages;
    if (msgs.length === 0) {
      wsEventsProcessed.current = 0;
      return;
    }
    if (wsEventsProcessed.current > msgs.length) {
      wsEventsProcessed.current = 0;
    }

    while (wsEventsProcessed.current < msgs.length) {
      const msg = msgs[wsEventsProcessed.current];
      wsEventsProcessed.current += 1;

      switch (msg.type) {
        case "session_started":
          setSessionActive(true);
          break;

        case "typing":
          setIsTyping(true);
          break;

        case "patient_response":
          setIsTyping(false);
          setChatMessages((prev) => [
            ...prev,
            {
              role: "patient",
              content: msg.content || "",
              emotion: msg.emotion,
              timestamp: Date.now(),
            },
          ]);
          if (msg.eval_update) {
            const ev = msg.eval_update;
            if (ev.checklist) setChecklist(ev.checklist);
            if (ev.completion_rate !== undefined) setCompletionRate(ev.completion_rate);
            if (ev.score !== undefined) setScore(ev.score);
          }
          break;

        case "eval_update":
          applyEvalPayload(msg);
          break;

        case "tutor_hint":
          setTutorHint({
            content: msg.content || "",
            level: msg.hint_level || "moderate",
          });
          setChatMessages((prev) => [
            ...prev,
            {
              role: "tutor",
              content: msg.content || "",
              hint_level: msg.hint_level,
              timestamp: Date.now(),
            },
          ]);
          break;

        case "session_summary":
          setIsTyping(false);
          setSessionActive(false);
          setSessionEnded(true);
          setSummary(msg);
          break;

        case "error":
          setIsTyping(false);
          break;

        default:
          break;
      }
    }
  }, [ws.messages, applyEvalPayload]);

  const handleSend = useCallback(
    (content: string) => {
      setIsTyping(true);
      setChatMessages((prev) => [
        ...prev,
        { role: "student", content, timestamp: Date.now() },
      ]);
      ws.sendMessage(content);
    },
    [ws]
  );

  const handleEnd = () => {
    ws.endSession();
  };

  const patientName = caseInfo?.patient_profile?.name || "患者";

  if (summary) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-6">训练报告</h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-blue-50 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">
                {summary.final_score?.toFixed(1)}
              </div>
              <div className="text-xs text-blue-500 mt-1">最终得分</div>
            </div>
            <div className="bg-green-50 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-green-600">
                {summary.completion_rate !== undefined
                  ? Math.round(summary.completion_rate * 100)
                  : 0}
                %
              </div>
              <div className="text-xs text-green-500 mt-1">完成率</div>
            </div>
            <div className="bg-purple-50 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-purple-600">
                {summary.student_messages}
              </div>
              <div className="text-xs text-purple-500 mt-1">提问次数</div>
            </div>
            <div className="bg-amber-50 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-amber-600">
                {summary.tutor_interventions_count}
              </div>
              <div className="text-xs text-amber-500 mt-1">导师干预</div>
            </div>
          </div>

          {summary.duration_seconds !== undefined && (
            <p className="text-sm text-slate-500 mb-4">
              用时: {Math.floor(summary.duration_seconds / 60)}分
              {summary.duration_seconds % 60}秒
            </p>
          )}

          {summary.strengths && summary.strengths.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-green-700 mb-2">
                优势
              </h4>
              <ul className="space-y-1">
                {summary.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-green-600 flex items-center gap-2">
                    <span>&#x2705;</span> {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.improvements && summary.improvements.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-amber-700 mb-2">
                待改进
              </h4>
              <ul className="space-y-1">
                {summary.improvements.map((s, i) => (
                  <li key={i} className="text-sm text-amber-600 flex items-center gap-2">
                    <span>&#x26A0;&#xFE0F;</span> {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.critical_missed && summary.critical_missed.length > 0 && (
            <div className="mb-6 bg-red-50 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-red-700 mb-2">
                遗漏的关键项目
              </h4>
              <ul className="space-y-1">
                {summary.critical_missed.map((s, i) => (
                  <li key={i} className="text-sm text-red-600">
                    - {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => navigate("/cases")}
              className="px-6 py-2.5 bg-medical text-white rounded-lg font-medium hover:bg-medical-dark transition-colors"
            >
              返回选择病例
            </button>
            <button
              onClick={() => navigate("/dashboard")}
              className="px-6 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              查看学习数据
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Left: Chat Area */}
      <div className="flex-1 flex flex-col bg-slate-50 min-w-0">
        {/* Top bar */}
        <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/cases")}
              className="text-slate-400 hover:text-slate-600 text-sm"
            >
              &larr; 返回
            </button>
            <div className="h-4 w-px bg-slate-200" />
            <div>
              <span className="text-sm font-medium text-slate-700">
                患者: {patientName}
              </span>
              <span className="text-xs text-slate-400 ml-2">
                {caseInfo?.patient_profile?.gender} / {caseInfo?.patient_profile?.age}岁
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Timer running={sessionActive} />
            {sessionActive && (
              <button
                onClick={handleEnd}
                className="px-4 py-1.5 border border-red-200 text-red-500 rounded-lg text-sm hover:bg-red-50 transition-colors"
              >
                结束问诊
              </button>
            )}
          </div>
        </div>

        {/* Tutor hint */}
        {tutorHint && (
          <TutorHint
            content={tutorHint.content}
            hintLevel={tutorHint.level}
            onDismiss={() => setTutorHint(null)}
          />
        )}

        {/* Chat */}
        <div className="flex-1 min-h-0">
          <ChatPanel
            messages={chatMessages}
            onSend={handleSend}
            disabled={!sessionActive}
            patientName={patientName}
            isTyping={isTyping}
          />
        </div>
      </div>

      {/* Right: Eval Sidebar */}
      <div className="w-80 border-l border-slate-200 bg-white overflow-hidden flex flex-col">
        <EvalSidebar
          checklist={checklist}
          completionRate={completionRate}
          score={score}
        />
      </div>
    </div>
  );
}
