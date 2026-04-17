interface ChecklistCategory {
  display_name: string;
  items: Record<
    string,
    { checked: boolean; weight: number; critical: boolean }
  >;
}

interface Props {
  checklist: Record<string, ChecklistCategory> | null;
  completionRate: number;
  score: number;
}

export default function EvalSidebar({ checklist, completionRate, score }: Props) {
  if (!checklist) {
    return (
      <div className="p-4 text-sm text-slate-400 text-center">
        等待会话开始...
      </div>
    );
  }

  const pct = Math.round(completionRate * 100);
  const circumference = 2 * Math.PI * 42;
  const dashOffset = circumference - (pct / 100) * circumference;

  return (
    <div className="p-4 overflow-y-auto h-full">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">问诊进度</h3>

      {/* Progress Ring */}
      <div className="flex flex-col items-center mb-6">
        <div className="relative w-28 h-28">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50" cy="50" r="42"
              fill="none" stroke="#e2e8f0" strokeWidth="8"
            />
            <circle
              cx="50" cy="50" r="42"
              fill="none"
              stroke={pct >= 80 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#3b82f6"}
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-slate-800">{pct}%</span>
            <span className="text-xs text-slate-400">信息采集</span>
          </div>
        </div>
      </div>

      {/* Category-level progress + only reveal checked items */}
      <div className="space-y-4">
        {Object.entries(checklist).map(([key, cat]) => {
          const items = Object.entries(cat.items);
          const checkedItems = items.filter(([, v]) => v.checked);
          const total = items.length;
          const checkedCount = checkedItems.length;
          const catPct = total > 0 ? Math.round((checkedCount / total) * 100) : 0;

          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold text-slate-600">
                  {cat.display_name}
                </h4>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${catPct}%`,
                        backgroundColor: catPct >= 80 ? "#22c55e" : catPct >= 50 ? "#f59e0b" : "#3b82f6",
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400 w-8 text-right">
                    {checkedCount}/{total}
                  </span>
                </div>
              </div>

              {/* Only show items that have been checked */}
              {checkedCount > 0 && (
                <div className="space-y-1">
                  {checkedItems.map(([name]) => (
                    <div
                      key={name}
                      className="flex items-center gap-2 text-xs px-2 py-1 rounded-lg bg-green-50 text-green-700 animate-[fadeIn_0.3s_ease-out]"
                    >
                      <span className="text-sm">{"\u2705"}</span>
                      <span>{name}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Unchecked items: show placeholder dots without names */}
              {checkedCount < total && (
                <div className="flex gap-1 mt-1 px-2">
                  {Array.from({ length: total - checkedCount }).map((_, i) => (
                    <span
                      key={i}
                      className="w-2 h-2 rounded-full bg-slate-200"
                      title="待采集的信息"
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Hint at bottom */}
      <div className="mt-6 p-3 bg-slate-50 rounded-xl">
        <p className="text-[11px] text-slate-400 leading-relaxed">
          灰色圆点代表尚未采集的信息。尝试通过系统的问诊来覆盖更多信息点。
        </p>
      </div>
    </div>
  );
}
