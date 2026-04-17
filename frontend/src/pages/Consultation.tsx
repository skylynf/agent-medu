import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useWebSocket, WSMessage } from "../hooks/useWebSocket";
import { api, UserResponse } from "../services/api";
import ChatPanel, { ChatMessage } from "../components/ChatPanel";
import EvalSidebar from "../components/EvalSidebar";
import TutorHint from "../components/TutorHint";
import Timer from "../components/Timer";
import WorksheetPanel from "../components/WorksheetPanel";

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
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [summary, setSummary] = useState<WSMessage | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isEnding, setIsEnding] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<"eval" | "worksheet">("eval");
  const isReconnectingRef = useRef(false);
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
    if (!ws.connected || !caseId) return;
    if (sessionEnded) return;
    if (isReconnectingRef.current && sessionId) {
      // 重连后优先尝试恢复原会话
      ws.resumeSession(sessionId);
      isReconnectingRef.current = false;
      return;
    }
    if (!sessionActive) {
      ws.startSession(caseId, { method: "multi_agent" });
    }
  }, [ws.connected, caseId, sessionActive, sessionEnded, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

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
          if (msg.session_id) setSessionId(msg.session_id);
          break;

        case "session_resumed":
          setSessionActive(true);
          setErrorBanner("已重新连接到原会话，可继续问诊。");
          break;

        case "session_expired":
          // 服务器侧已不再持有该会话 → 用 case 重新开一局
          setSessionActive(false);
          setSessionId(null);
          setChatMessages([]);
          setChecklist(null);
          setCompletionRate(0);
          setScore(0);
          setErrorBanner("原会话已失效，已为你开启新的问诊。");
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
          setIsEnding(false);
          setSessionActive(false);
          setSessionEnded(true);
          setSummary(msg);
          break;

        case "error":
          setIsTyping(false);
          setIsEnding(false);
          setErrorBanner(msg.content || "本轮处理失败，请稍后重试。");
          break;

        default:
          break;
      }
    }
  }, [ws.messages, applyEvalPayload]);

  const handleSend = useCallback(
    (content: string) => {
      setErrorBanner(null);
      setIsTyping(true);
      setChatMessages((prev) => [
        ...prev,
        { role: "student", content, timestamp: Date.now() },
      ]);
      const ok = ws.sendMessage(content);
      if (!ok) {
        setIsTyping(false);
        setErrorBanner("连接已断开，无法发送。请点击「重新连接」后再试。");
      }
    },
    [ws]
  );

  const handleReconnect = useCallback(() => {
    setErrorBanner(null);
    setIsTyping(false);
    isReconnectingRef.current = !!sessionId;
    ws.disconnect();
    setTimeout(() => ws.connect(), 150);
  }, [ws, sessionId]);

  const wsBroken =
    sessionActive && !sessionEnded && (ws.status === "error" || ws.status === "closed");

  const handleEnd = useCallback(() => {
    if (isEnding) return;
    if (!window.confirm("确认结束本次问诊？提交后将由系统对全程对话与临床表单进行总评，过程约需 10–30 秒。")) {
      return;
    }
    setErrorBanner(null);
    setIsEnding(true);
    const ok = ws.endSession();
    if (!ok) {
      setIsEnding(false);
      setErrorBanner("连接已断开，无法提交结束指令。请点击「重新连接」后再试。");
    }
  }, [ws, isEnding]);

  const patientName = caseInfo?.patient_profile?.name || "患者";

  if (summary) {
    const hasFinalEval = summary.holistic_scores !== undefined;
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

          {hasFinalEval && (
            <div className="mb-6 border border-slate-200 rounded-xl p-5 space-y-4">
              <h4 className="text-sm font-semibold text-slate-700">
                临床推理总评（基于对话 + 临床表单）
              </h4>
              {summary.holistic_scores && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {(
                    [
                      ["history_completeness", "病史完整性"],
                      ["communication", "医患沟通"],
                      ["clinical_reasoning", "临床推理"],
                      ["diagnostic_accuracy", "诊断准确性"],
                    ] as const
                  ).map(([k, label]) => (
                    <div key={k} className="bg-slate-50 rounded-lg p-3 text-center">
                      <div className="text-xl font-bold text-blue-600">
                        {summary.holistic_scores?.[k] ?? "—"}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>
              )}
              <div
                className={`rounded-lg p-3 text-sm ${
                  summary.diagnosis_correct
                    ? "bg-green-50 text-green-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                <span className="font-medium">学生诊断：</span>
                {summary.diagnosis_given || "未给出"}
                <span className="ml-2 text-xs">
                  {summary.diagnosis_correct ? "（方向正确）" : "（不正确或未明确）"}
                </span>
              </div>
              {summary.narrative_feedback && (
                <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {summary.narrative_feedback}
                </p>
              )}
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
    <div className="flex h-[calc(100vh-57px)] relative">
      {isEnding && <EndingOverlay />}
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
                disabled={isEnding}
                className="px-4 py-1.5 border border-red-200 text-red-500 rounded-lg text-sm hover:bg-red-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isEnding ? "正在生成报告..." : "结束问诊"}
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

        {/* Connection / error banner */}
        {(wsBroken || errorBanner) && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between">
            <div className="text-sm text-amber-800 flex items-center gap-2">
              {wsBroken ? (
                <>
                  <span>&#9888;</span>
                  <span>与服务器的连接已断开。</span>
                </>
              ) : (
                <>
                  <span>&#9888;</span>
                  <span>{errorBanner}</span>
                </>
              )}
            </div>
            {wsBroken && (
              <button
                onClick={handleReconnect}
                className="text-sm px-3 py-1 bg-amber-600 text-white rounded hover:bg-amber-700"
              >
                重新连接
              </button>
            )}
            {!wsBroken && errorBanner && (
              <button
                onClick={() => setErrorBanner(null)}
                className="text-xs text-amber-700 hover:underline"
              >
                忽略
              </button>
            )}
          </div>
        )}

        {/* Chat */}
        <div className="flex-1 min-h-0">
          <ChatPanel
            messages={chatMessages}
            onSend={handleSend}
            disabled={!sessionActive || wsBroken}
            patientName={patientName}
            isTyping={isTyping}
          />
        </div>
      </div>

      {/* Right: Eval / Worksheet Sidebar with tabs */}
      <div className="w-96 border-l border-slate-200 bg-white overflow-hidden flex flex-col">
        <div className="flex border-b border-slate-100">
          <button
            onClick={() => setSidebarTab("eval")}
            className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              sidebarTab === "eval"
                ? "border-medical text-medical"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            评估进度
          </button>
          <button
            onClick={() => setSidebarTab("worksheet")}
            className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              sidebarTab === "worksheet"
                ? "border-medical text-medical"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            临床表单
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden">
          {sidebarTab === "eval" ? (
            <EvalSidebar
              checklist={checklist}
              completionRate={completionRate}
              score={score}
            />
          ) : (
            <WorksheetPanel sessionId={sessionId} readOnly={!sessionActive} />
          )}
        </div>
      </div>
    </div>
  );
}

function EndingOverlay() {
  return (
    <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-sm flex items-center justify-center">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl px-8 py-6 flex items-center gap-4 max-w-sm">
        <div className="w-8 h-8 border-4 border-medical/30 border-t-medical rounded-full animate-spin" />
        <div>
          <div className="text-sm font-semibold text-slate-700">
            正在生成本次问诊总评...
          </div>
          <div className="text-xs text-slate-500 mt-1 leading-relaxed">
            系统正基于全程对话与临床表单做整体评估，约需 10–30 秒，请勿关闭此页面。
          </div>
        </div>
      </div>
    </div>
  );
}
