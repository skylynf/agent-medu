import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, SurveyInstrument } from "../services/api";

interface SubmitState {
  status: "idle" | "submitting" | "ok" | "error";
  message?: string;
  scoring?: any;
}

export default function PostTest() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const navigate = useNavigate();

  const [instruments, setInstruments] = useState<SurveyInstrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [responses, setResponses] = useState<Record<string, Record<string, any>>>({});
  const [state, setState] = useState<Record<string, SubmitState>>({});

  useEffect(() => {
    api.surveys
      .instruments()
      .then(setInstruments)
      .catch((e) => setError(e.message || "加载问卷失败"))
      .finally(() => setLoading(false));
  }, []);

  const susInstrument = useMemo(
    () => instruments.find((i) => i.instrument === "sus"),
    [instruments]
  );
  const uesInstrument = useMemo(
    () => instruments.find((i) => i.instrument === "ues"),
    [instruments]
  );
  const openInstrument = useMemo(
    () => instruments.find((i) => i.instrument === "open_ended"),
    [instruments]
  );

  const setAnswer = (instrument: string, qid: string, value: any) => {
    setResponses((prev) => ({
      ...prev,
      [instrument]: { ...(prev[instrument] || {}), [qid]: value },
    }));
  };

  const submit = async (instrument: string) => {
    const inst = instruments.find((i) => i.instrument === instrument);
    if (!inst) return;
    const data = responses[instrument] || {};
    setState((prev) => ({ ...prev, [instrument]: { status: "submitting" } }));
    try {
      const resp = await api.surveys.submit({
        instrument,
        related_session_id: sessionId,
        responses: data,
      });
      setState((prev) => ({
        ...prev,
        [instrument]: { status: "ok", scoring: resp.scoring },
      }));
    } catch (e: any) {
      setState((prev) => ({
        ...prev,
        [instrument]: { status: "error", message: e.message || "提交失败" },
      }));
    }
  };

  if (loading) {
    return <div className="max-w-3xl mx-auto px-6 py-10 text-slate-500">加载问卷...</div>;
  }
  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10 text-red-600">{error}</div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">后测问卷</h2>
        <p className="text-slate-500 mt-1">
          请在完成全部学习与考试任务后填写下列问卷。各问卷可独立提交。
          {sessionId && (
            <span className="ml-1 text-xs text-slate-400">
              （已关联 session: {sessionId.slice(0, 8)}…）
            </span>
          )}
        </p>
      </div>

      {susInstrument && (
        <SurveyCard
          instrument={susInstrument}
          values={responses["sus"] || {}}
          onChange={(qid, val) => setAnswer("sus", qid, val)}
          onSubmit={() => submit("sus")}
          state={state["sus"]}
          render={(item) => (
            <LikertRow
              key={item.id}
              item={item}
              scale={susInstrument.scale}
              value={(responses["sus"] || {})[item.id]}
              onChange={(v) => setAnswer("sus", item.id, v)}
            />
          )}
        />
      )}

      {uesInstrument && (
        <SurveyCard
          instrument={uesInstrument}
          values={responses["ues"] || {}}
          onChange={(qid, val) => setAnswer("ues", qid, val)}
          onSubmit={() => submit("ues")}
          state={state["ues"]}
          render={(item) => (
            <LikertRow
              key={item.id}
              item={item}
              scale={uesInstrument.scale}
              value={(responses["ues"] || {})[item.id]}
              onChange={(v) => setAnswer("ues", item.id, v)}
            />
          )}
        />
      )}

      {openInstrument && (
        <SurveyCard
          instrument={openInstrument}
          values={responses["open_ended"] || {}}
          onChange={(qid, val) => setAnswer("open_ended", qid, val)}
          onSubmit={() => submit("open_ended")}
          state={state["open_ended"]}
          render={(item) => (
            <div key={item.id}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {item.text}
              </label>
              <textarea
                rows={3}
                value={(responses["open_ended"] || {})[item.id] || ""}
                placeholder={item.placeholder || ""}
                onChange={(e) => setAnswer("open_ended", item.id, e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical"
              />
            </div>
          )}
        />
      )}

      <div className="flex gap-3 pt-2">
        <button
          onClick={() => navigate("/")}
          className="px-5 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
        >
          返回主页
        </button>
      </div>
    </div>
  );
}

interface SurveyCardProps {
  instrument: SurveyInstrument;
  values: Record<string, any>;
  onChange: (qid: string, value: any) => void;
  onSubmit: () => void;
  state?: SubmitState;
  render: (item: SurveyInstrument["items"][number]) => React.ReactNode;
}

function SurveyCard({ instrument, onSubmit, state, render }: SurveyCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <h3 className="text-lg font-semibold text-slate-800">{instrument.display_name}</h3>
      {instrument.description && (
        <p className="text-xs text-slate-500 mt-1 whitespace-pre-wrap">
          {instrument.description}
        </p>
      )}

      <div className="mt-5 space-y-4">
        {instrument.items.map((item) => render(item))}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <div className="text-xs text-slate-400">
          {state?.status === "ok" && (
            <span className="text-green-600">
              提交成功
              {state.scoring?.sus_score !== undefined && state.scoring?.sus_score !== null && (
                <> · SUS 总分 {Number(state.scoring.sus_score).toFixed(1)}</>
              )}
              {state.scoring?.ues_overall !== undefined && state.scoring?.ues_overall !== null && (
                <>
                  {" "}
                  · UES 总体 {Number(state.scoring.ues_overall).toFixed(2)}（FA{" "}
                  {Number(state.scoring.fa_mean).toFixed(2)} / PU {Number(state.scoring.pu_mean).toFixed(2)} / AE{" "}
                  {Number(state.scoring.ae_mean).toFixed(2)} / RW {Number(state.scoring.rw_mean).toFixed(2)}）
                </>
              )}
            </span>
          )}
          {state?.status === "error" && (
            <span className="text-red-600">{state.message}</span>
          )}
        </div>
        <button
          onClick={onSubmit}
          disabled={state?.status === "submitting"}
          className="px-4 py-2 bg-medical text-white rounded-lg text-sm font-medium hover:bg-medical-dark transition-colors disabled:opacity-50"
        >
          {state?.status === "submitting" ? "提交中..." : "提交问卷"}
        </button>
      </div>
    </div>
  );
}

interface LikertRowProps {
  item: SurveyInstrument["items"][number];
  scale?: SurveyInstrument["scale"];
  value: any;
  onChange: (v: number) => void;
}

function LikertRow({ item, scale, value, onChange }: LikertRowProps) {
  const min = scale?.min ?? 1;
  const max = scale?.max ?? 5;
  const labels = scale?.labels || {};
  const opts: number[] = [];
  for (let v = min; v <= max; v++) opts.push(v);

  return (
    <div className="border border-slate-100 rounded-lg p-3">
      <div className="text-sm text-slate-700 mb-2">{item.text}</div>
      <div className="flex items-center gap-2 flex-wrap">
        {opts.map((v) => (
          <label
            key={v}
            className={`flex flex-col items-center px-2 py-1.5 rounded-lg cursor-pointer text-xs border transition-colors ${
              value === v
                ? "border-medical bg-medical/10 text-medical font-semibold"
                : "border-slate-200 text-slate-500 hover:bg-slate-50"
            }`}
          >
            <input
              type="radio"
              name={item.id}
              value={v}
              checked={value === v}
              onChange={() => onChange(v)}
              className="sr-only"
            />
            <span className="text-base font-medium">{v}</span>
            <span className="text-[10px] mt-0.5">{labels[String(v)] || ""}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
