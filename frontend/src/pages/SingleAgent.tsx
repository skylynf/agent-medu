import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useWebSocket, WSMessage } from "../hooks/useWebSocket";
import { api, UserResponse } from "../services/api";
import ChatPanel, { ChatMessage } from "../components/ChatPanel";
import Timer from "../components/Timer";
import WorksheetPanel from "../components/WorksheetPanel";

interface Props {
  user: UserResponse;
}

/**
 * SingleAgent (SA) — 仅与 AI-SP 自由对话。
 * 不显示评分、不显示导师提示，结束时只回顾用时与发问次数。
 */
export default function SingleAgent(_: Props) {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const ws = useWebSocket();

  const [caseInfo, setCaseInfo] = useState<any | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [summary, setSummary] = useState<WSMessage | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const wsEventsProcessed = useRef(0);
  const isReconnectingRef = useRef(false);

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
      ws.resumeSession(sessionId);
      isReconnectingRef.current = false;
      return;
    }
    if (!sessionActive) {
      ws.startSession(caseId, { method: "single_agent" });
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
          setSessionActive(false);
          setSessionId(null);
          setChatMessages([]);
          setErrorBanner("原会话已失效，已为你开启新的练习。");
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
  }, [ws.messages]);

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

  const handleEnd = useCallback(() => {
    if (isEnding) return;
    if (!window.confirm("确认结束本次单智能体练习吗？结束后无法继续追加问诊。")) {
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

  const handleReconnect = useCallback(() => {
    setErrorBanner(null);
    setIsTyping(false);
    isReconnectingRef.current = !!sessionId;
    ws.disconnect();
    setTimeout(() => ws.connect(), 150);
  }, [ws, sessionId]);

  const wsBroken =
    sessionActive && !sessionEnded && (ws.status === "error" || ws.status === "closed");

  const patientName = caseInfo?.patient_profile?.name || "患者";

  if (summary) {
    const dur = summary.duration_seconds ?? 0;
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-slate-800">练习已结束</h2>
            <span className="px-3 py-1 bg-sky-50 text-sky-700 rounded-full text-xs font-medium">
              Single-Agent Mode
            </span>
          </div>

          <p className="text-slate-600 leading-relaxed mb-6">
            本次为 <strong>单智能体（SA）</strong>自由对话练习，按研究方案不向你显示评分与诊断反馈。
            如需复盘可前往「学习数据」查看本次会话基本元数据。
          </p>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
            <Card label="提问次数" value={String(summary.student_messages ?? 0)} color="text-purple-600" />
            <Card
              label="对话总轮数"
              value={String(summary.total_messages ?? 0)}
              color="text-blue-600"
            />
            <Card
              label="用时"
              value={`${Math.floor(dur / 60)} 分 ${dur % 60} 秒`}
              color="text-amber-600"
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => navigate("/")}
              className="px-5 py-2.5 bg-medical text-white rounded-lg font-medium"
            >
              返回主页
            </button>
            <button
              onClick={() =>
                navigate(sessionId ? `/post-test?session_id=${sessionId}` : "/post-test")
              }
              className="px-5 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            >
              前往后测问卷
            </button>
            <button
              onClick={() => navigate("/dashboard")}
              className="px-5 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            >
              查看学习数据
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-57px)] bg-slate-50 relative">
      {isEnding && (
        <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-xl px-8 py-6 flex items-center gap-4 max-w-sm">
            <div className="w-8 h-8 border-4 border-medical/30 border-t-medical rounded-full animate-spin" />
            <div>
              <div className="text-sm font-semibold text-slate-700">正在结束本次练习...</div>
              <div className="text-xs text-slate-500 mt-1 leading-relaxed">即将跳转至练习回顾页面。</div>
            </div>
          </div>
        </div>
      )}
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/cases?method=single_agent")}
            className="text-slate-400 hover:text-slate-600 text-sm"
          >
            &larr; 返回
          </button>
          <div className="h-4 w-px bg-slate-200" />
          <div>
            <span className="text-sm font-medium text-slate-700">
              单智能体模式 · 患者 {patientName}
            </span>
            <span className="text-xs text-slate-400 ml-2">
              本模式仅与 AI-SP 自由对话，不显示评分与导师提示
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Timer running={sessionActive} />
          {sessionActive && (
            <button
              onClick={handleEnd}
              disabled={isEnding}
              className="px-4 py-1.5 border border-sky-300 text-sky-700 rounded-lg text-sm hover:bg-sky-50 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isEnding ? "结束中..." : "结束本次练习"}
            </button>
          )}
        </div>
      </div>

      {(wsBroken || errorBanner) && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between">
          <div className="text-sm text-amber-800 flex items-center gap-2">
            <span>&#9888;</span>
            <span>{wsBroken ? "与服务器的连接已断开。" : errorBanner}</span>
          </div>
          {wsBroken ? (
            <button
              onClick={handleReconnect}
              className="text-sm px-3 py-1 bg-amber-600 text-white rounded hover:bg-amber-700"
            >
              重新连接
            </button>
          ) : (
            errorBanner && (
              <button
                onClick={() => setErrorBanner(null)}
                className="text-xs text-amber-700 hover:underline"
              >
                忽略
              </button>
            )
          )}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0 flex flex-col">
          <ChatPanel
            messages={chatMessages}
            onSend={handleSend}
            disabled={!sessionActive || wsBroken}
            patientName={patientName}
            isTyping={isTyping}
          />
        </div>
        <div className="w-96 border-l border-slate-200 bg-white overflow-hidden flex flex-col">
          <WorksheetPanel sessionId={sessionId} readOnly={!sessionActive} />
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-slate-50 rounded-xl p-4 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}
