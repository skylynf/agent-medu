import { useEffect, useMemo, useRef, useState } from "react";
import { api, WorksheetData } from "../services/api";

interface FieldDef {
  key: keyof WorksheetData;
  label: string;
  placeholder: string;
  rows?: number;
}

const FIELDS: FieldDef[] = [
  {
    key: "chief_complaint",
    label: "主诉概括",
    placeholder: "例：上腹痛 6 小时，呕吐 2 次。",
    rows: 2,
  },
  {
    key: "hpi",
    label: "现病史汇总",
    placeholder: "起病诱因、性质、放射、伴随症状、加重 / 缓解因素、既往类似发作等。",
    rows: 4,
  },
  {
    key: "past_history",
    label: "既往史 / 个人史 / 家族史",
    placeholder: "高血压、糖尿病、手术史、药物 / 食物过敏、烟酒、家族史等。",
    rows: 3,
  },
  {
    key: "physical_exam",
    label: "体格检查重点（如已采集）",
    placeholder: "生命体征、腹部查体、压痛 / 反跳痛、Murphy 征等。",
    rows: 2,
  },
  {
    key: "differentials",
    label: "鉴别诊断（每行一个）",
    placeholder: "急性胆囊炎\n急性胰腺炎\n胃十二指肠穿孔\n...",
    rows: 4,
  },
  {
    key: "diagnosis",
    label: "最可能诊断",
    placeholder: "你的初步判断。",
    rows: 2,
  },
  {
    key: "diagnostic_reasoning",
    label: "诊断依据 / 推理过程",
    placeholder: "结合你采集到的关键信息说明为什么倾向于该诊断、为什么排除其他鉴别。",
    rows: 4,
  },
  {
    key: "investigations",
    label: "下一步检查",
    placeholder: "实验室、影像、特殊检查及其依据。",
    rows: 3,
  },
  {
    key: "management",
    label: "处置 / 治疗计划",
    placeholder: "急诊处置、专科会诊、手术 / 保守治疗、患者教育等。",
    rows: 3,
  },
];

interface Props {
  sessionId: string | null;
  /** 会话已结束 → 表单只读 */
  readOnly?: boolean;
}

type SaveStatus = "idle" | "saving" | "saved" | "error";

const SAVE_DEBOUNCE_MS = 800;

export default function WorksheetPanel({ sessionId, readOnly = false }: Props) {
  const [data, setData] = useState<WorksheetData>({});
  const [loaded, setLoaded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const lastSavedRef = useRef<string>("");

  // 拉取已有 worksheet
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api.sessions
      .getWorksheet(sessionId)
      .then((resp) => {
        if (cancelled) return;
        const ws = resp.worksheet || {};
        setData(ws);
        lastSavedRef.current = JSON.stringify(stripMeta(ws));
        setLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // 防抖保存
  useEffect(() => {
    if (!sessionId || !loaded || readOnly) return;
    const cur = JSON.stringify(stripMeta(data));
    if (cur === lastSavedRef.current) return;

    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
    }
    setSaveStatus("saving");
    debounceRef.current = window.setTimeout(async () => {
      try {
        await api.sessions.saveWorksheet(sessionId, stripMeta(data));
        lastSavedRef.current = cur;
        setSaveStatus("saved");
        setErrorMsg(null);
      } catch (e: any) {
        setSaveStatus("error");
        setErrorMsg(e?.message || "保存失败");
      }
    }, SAVE_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
      }
    };
  }, [data, sessionId, loaded, readOnly]);

  const filledCount = useMemo(
    () =>
      FIELDS.reduce((acc, f) => {
        const v = (data[f.key] as string) || "";
        return v.trim() ? acc + 1 : acc;
      }, 0),
    [data]
  );

  const handleChange = (key: keyof WorksheetData, value: string) => {
    setData((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-2 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">临床推理表单</h3>
          <span className="text-[11px] text-slate-400">
            {filledCount}/{FIELDS.length} 已填写
          </span>
        </div>
        <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
          边问诊边记录你的鉴别诊断与推理过程。本表单将与对话记录一并提交终评。
        </p>
        <div className="mt-2 text-[11px] h-4">
          {!sessionId && (
            <span className="text-slate-300">等待会话开始...</span>
          )}
          {sessionId && saveStatus === "saving" && (
            <span className="text-blue-500">保存中...</span>
          )}
          {sessionId && saveStatus === "saved" && (
            <span className="text-green-600">已自动保存</span>
          )}
          {sessionId && saveStatus === "error" && (
            <span className="text-red-500">保存失败：{errorMsg}</span>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-4">
        {FIELDS.map((f) => (
          <div key={f.key as string}>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              {f.label}
            </label>
            <textarea
              className="w-full text-sm border border-slate-200 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-medical/40 disabled:bg-slate-50 disabled:text-slate-500 resize-y"
              rows={f.rows ?? 3}
              placeholder={f.placeholder}
              value={(data[f.key] as string) || ""}
              onChange={(e) => handleChange(f.key, e.target.value)}
              disabled={!sessionId || readOnly}
              maxLength={4000}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function stripMeta(ws: WorksheetData): WorksheetData {
  const { _updated_at, ...rest } = ws;
  return rest;
}
