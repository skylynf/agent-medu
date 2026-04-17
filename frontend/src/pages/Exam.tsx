import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import { useWebSocket, WSMessage } from "../hooks/useWebSocket";
import { api, FinalEvaluation, UserResponse } from "../services/api";
import ChatPanel, { ChatMessage } from "../components/ChatPanel";
import Timer from "../components/Timer";
import WorksheetPanel from "../components/WorksheetPanel";

interface Props {
  user: UserResponse;
}

const HOLISTIC_LABELS: Record<string, string> = {
  history_completeness: "病史完整性",
  communication: "医患沟通",
  clinical_reasoning: "临床推理",
  diagnostic_accuracy: "诊断准确性",
};

export default function Exam(_: Props) {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const ws = useWebSocket();

  const [caseInfo, setCaseInfo] = useState<any | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [summary, setSummary] = useState<WSMessage | null>(null);
  const [finalEval, setFinalEval] = useState<FinalEvaluation | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [waitingFinal, setWaitingFinal] = useState(false);
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
      ws.startSession(caseId, { method: "exam" });
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
          setErrorBanner("原考试会话已失效，已为你开启新的考试。");
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
          // Backend already wrote FinalEvaluation; pull it for canonical display.
          if (msg.session_id) {
            setWaitingFinal(true);
            api.sessions
              .finalEvaluation(msg.session_id)
              .then(setFinalEval)
              .catch(console.error)
              .finally(() => setWaitingFinal(false));
          }
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
    if (!window.confirm("确认要结束考试并提交进行总评吗？提交后无法再次问诊，总评通常较快完成，最长约 2 分钟。")) {
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
    const radarData = finalEval
      ? Object.entries(finalEval.holistic_scores).map(([k, v]) => ({
          dimension: HOLISTIC_LABELS[k] || k,
          score: v,
          fullMark: 5,
        }))
      : [];
    const checklistEntries = finalEval
      ? Object.entries(finalEval.checklist_results)
      : [];
    const checkedCount = checklistEntries.filter(([_, v]) => v).length;

    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-slate-800">考试总评报告</h2>
            <span className="px-3 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium">
              Exam Mode
            </span>
          </div>

          {waitingFinal && (
            <div className="text-slate-500 text-sm mb-4">正在生成详细总评...</div>
          )}

          {finalEval ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-5">
                  <div className="text-xs text-blue-700 mb-2">4 维 OSCE 评分</div>
                  <div className="h-64">
                    <ResponsiveContainer>
                      <RadarChart data={radarData}>
                        <PolarGrid />
                        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
                        <PolarRadiusAxis angle={90} domain={[0, 5]} tickCount={6} />
                        <Radar
                          name="得分"
                          dataKey="score"
                          stroke="#2563eb"
                          fill="#2563eb"
                          fillOpacity={0.4}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className={`rounded-xl p-4 ${finalEval.diagnosis_correct ? "bg-green-50" : "bg-red-50"}`}>
                    <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
                      学生给出的主诊断
                    </div>
                    <div className="text-lg font-semibold text-slate-800">
                      {finalEval.diagnosis_given || "未给出"}
                    </div>
                    <div className={`text-sm mt-1 ${finalEval.diagnosis_correct ? "text-green-700" : "text-red-700"}`}>
                      {finalEval.diagnosis_correct ? "诊断方向正确" : "诊断不正确或未明确"}
                    </div>
                    {finalEval.differentials_given.length > 0 && (
                      <div className="text-xs text-slate-600 mt-2">
                        鉴别: {finalEval.differentials_given.join("，")}
                      </div>
                    )}
                  </div>

                  <div className="rounded-xl p-4 bg-slate-50">
                    <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
                      Checklist 命中
                    </div>
                    <div className="text-lg font-semibold text-slate-800">
                      {checkedCount} / {checklistEntries.length}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      用时 {summary.duration_seconds !== undefined
                        ? `${Math.floor(summary.duration_seconds / 60)} 分 ${summary.duration_seconds % 60} 秒`
                        : "—"}
                      ，共发问 {summary.student_messages} 次
                    </div>
                  </div>
                </div>
              </div>

              {finalEval.narrative_feedback && (
                <div className="mb-6 bg-white border border-slate-200 rounded-xl p-5">
                  <h4 className="text-sm font-semibold text-slate-700 mb-2">教师整体反馈</h4>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {finalEval.narrative_feedback}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                {finalEval.strengths.length > 0 && (
                  <div className="bg-green-50 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-green-700 mb-2">优势</h4>
                    <ul className="space-y-1">
                      {finalEval.strengths.map((s, i) => (
                        <li key={i} className="text-sm text-green-700">
                          + {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {finalEval.improvements.length > 0 && (
                  <div className="bg-amber-50 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-amber-700 mb-2">待改进</h4>
                    <ul className="space-y-1">
                      {finalEval.improvements.map((s, i) => (
                        <li key={i} className="text-sm text-amber-700">
                          - {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="mb-6">
                <h4 className="text-sm font-semibold text-slate-700 mb-2">
                  Checklist 详情
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-sm">
                  {checklistEntries.map(([name, hit]) => (
                    <div
                      key={name}
                      className={`flex items-start gap-2 px-2 py-1 rounded ${
                        hit ? "text-slate-700" : "text-slate-400"
                      }`}
                    >
                      <span>{hit ? "[x]" : "[ ]"}</span>
                      <span>{name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <Card label="得分" value={summary.final_score?.toFixed(1) ?? "—"} color="text-blue-600" />
              <Card
                label="完成率"
                value={
                  summary.completion_rate !== undefined
                    ? `${Math.round(summary.completion_rate * 100)}%`
                    : "—"
                }
                color="text-green-600"
              />
              <Card label="提问次数" value={String(summary.student_messages ?? 0)} color="text-purple-600" />
              <Card
                label="用时"
                value={
                  summary.duration_seconds !== undefined
                    ? `${Math.floor(summary.duration_seconds / 60)}m`
                    : "—"
                }
                color="text-amber-600"
              />
            </div>
          )}

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
      {isEnding && <EndingOverlay text="正在生成考试总评..." subtext="系统正基于全程对话与临床表单做整体评估（OSCE 4 维 + 诊断），最长约 2 分钟，请勿关闭此页面。" />}
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/cases?method=exam")}
            className="text-slate-400 hover:text-slate-600 text-sm"
          >
            &larr; 返回
          </button>
          <div className="h-4 w-px bg-slate-200" />
          <div>
            <span className="text-sm font-medium text-slate-700">
              考试模式 · 患者 {patientName}
            </span>
            <span className="text-xs text-slate-400 ml-2">
              本模式不显示评分与导师提示
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Timer running={sessionActive} />
          {sessionActive && (
            <button
              onClick={handleEnd}
              disabled={isEnding}
              className="px-4 py-1.5 border border-amber-300 text-amber-700 rounded-lg text-sm hover:bg-amber-50 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isEnding ? "正在生成总评..." : "结束并提交总评"}
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

function EndingOverlay({ text, subtext }: { text: string; subtext: string }) {
  return (
    <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-sm flex items-center justify-center">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl px-8 py-6 flex items-center gap-4 max-w-sm">
        <div className="w-8 h-8 border-4 border-medical/30 border-t-medical rounded-full animate-spin" />
        <div>
          <div className="text-sm font-semibold text-slate-700">{text}</div>
          <div className="text-xs text-slate-500 mt-1 leading-relaxed">{subtext}</div>
        </div>
      </div>
    </div>
  );
}
