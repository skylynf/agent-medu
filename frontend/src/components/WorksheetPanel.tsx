import { useEffect, useMemo, useRef, useState } from "react";
import { api, WorksheetData } from "../services/api";

interface FieldDef {
  key: keyof WorksheetData;
  label: string;
  rows?: number;
}

// 精简至 4 个核心字段：鉴别诊断、最可能诊断、诊断依据、处置计划。
// 主诉 / 现病史 / 既往史 / 体格检查 / 辅助检查 等内容可由 final_evaluator
// 直接从对话记录中提取，不再要求学生重复填写。
const FIELDS: FieldDef[] = [
  { key: "differentials", label: "鉴别诊断（每行一个）", rows: 4 },
  { key: "diagnosis", label: "最可能诊断", rows: 2 },
  { key: "diagnostic_reasoning", label: "诊断依据", rows: 4 },
  { key: "management", label: "处置 / 治疗计划", rows: 3 },
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
