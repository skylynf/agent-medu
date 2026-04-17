import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ControlStage } from "../services/api";

export default function ControlLearning() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stage, setStage] = useState<ControlStage | null>(null);
  const [totalStages, setTotalStages] = useState(4);
  const [studentInput, setStudentInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [history, setHistory] = useState<{ index: number; title: string; input: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    api.control
      .start(caseId)
      .then((resp) => {
        setSessionId(resp.session_id);
        setStage(resp.current_stage);
        setTotalStages(resp.total_stages);
      })
      .catch((e) => setError(e.message || "启动失败"))
      .finally(() => setLoading(false));
  }, [caseId]);

  const handleSubmit = async () => {
    if (!sessionId || !stage) return;
    if (stage.requires_input && studentInput.trim().length === 0) {
      setError("请先填写本阶段的回答再提交");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const resp = await api.control.submit(sessionId, stage.stage_index, studentInput);
      setHistory((prev) => [
        ...prev,
        {
          index: stage.stage_index,
          title: stage.title,
          input: studentInput,
        },
      ]);
      setStudentInput("");
      if (resp.completed) {
        setCompleted(true);
        setStage(null);
      } else {
        setStage(resp.next_stage);
      }
    } catch (e: any) {
      setError(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10 text-slate-500">加载对照学习...</div>
    );
  }

  if (error && !stage && !completed) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
          {error}
          <div className="mt-4">
            <button
              onClick={() => navigate("/cases?method=control")}
              className="px-4 py-2 bg-medical text-white rounded-lg text-sm"
            >
              返回病例列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="bg-white rounded-2xl border border-slate-200 p-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-2">对照学习已完成</h2>
          <p className="text-slate-500 mb-6">
            你的所有阶段输入已经记录在系统中，将用于研究分析。请按照实验指引继续完成剩余环节。
          </p>

          <h3 className="text-sm font-semibold text-slate-700 mb-3">你的阶段输入回顾</h3>
          <div className="space-y-3">
            {history.map((h) => (
              <div key={h.index} className="border border-slate-200 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">{h.title}</div>
                <div className="text-sm text-slate-700 whitespace-pre-wrap">
                  {h.input || <span className="text-slate-400">（未填写）</span>}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 flex gap-3">
            <button
              onClick={() => navigate("/")}
              className="px-5 py-2 bg-medical text-white rounded-lg text-sm"
            >
              返回主页
            </button>
            <button
              onClick={() => navigate("/post-test")}
              className="px-5 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            >
              前往后测问卷
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!stage) return null;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate("/cases?method=control")}
          className="text-sm text-slate-400 hover:text-slate-600"
        >
          &larr; 返回
        </button>
        <div className="text-sm text-slate-500">
          阶段 {stage.stage_index + 1} / {totalStages}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-8">
        <h2 className="text-xl font-semibold text-slate-800 mb-1">{stage.title}</h2>
        <p className="text-xs text-slate-400 mb-5">
          请仔细阅读以下信息，{stage.requires_input ? "然后在右侧填写你的回答" : "本阶段为答案揭示，无需填写"}。
        </p>

        <div className="bg-slate-50 rounded-xl p-5 whitespace-pre-wrap text-sm leading-relaxed text-slate-700 mb-6">
          {stage.disclosed_content}
        </div>

        {stage.requires_input && stage.prompt_to_student && (
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              {stage.prompt_to_student}
            </label>
            <textarea
              value={studentInput}
              onChange={(e) => setStudentInput(e.target.value)}
              rows={6}
              placeholder="在此填写你的问题 / 鉴别诊断 / 处置..."
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical"
              disabled={submitting}
            />
          </div>
        )}

        {error && (
          <div className="mt-3 text-sm text-red-600">{error}</div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-5 py-2.5 bg-medical text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-medical-dark transition-colors"
          >
            {stage.is_final ? "完成对照学习" : "提交并进入下一阶段"}
          </button>
        </div>
      </div>
    </div>
  );
}
