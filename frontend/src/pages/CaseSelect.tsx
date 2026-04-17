import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, CaseSummary, MethodId } from "../services/api";

const difficultyLabels: Record<number, string> = {
  1: "基础",
  2: "中等",
  3: "进阶",
  4: "挑战",
};

const difficultyColors: Record<number, string> = {
  1: "bg-green-100 text-green-700",
  2: "bg-blue-100 text-blue-700",
  3: "bg-orange-100 text-orange-700",
  4: "bg-red-100 text-red-700",
};

const METHOD_LABELS: Record<MethodId, string> = {
  multi_agent: "多智能体学习 (MA)",
  control: "对照学习 (CT)",
  exam: "考试方法 (Exam)",
  post_test: "后测问卷",
};

const METHOD_BADGE_BG: Record<MethodId, string> = {
  multi_agent: "bg-blue-600",
  control: "bg-emerald-600",
  exam: "bg-amber-600",
  post_test: "bg-purple-600",
};

function getRouteForCase(method: MethodId, caseId: string): string {
  switch (method) {
    case "multi_agent":
      return `/consultation/${caseId}`;
    case "control":
      return `/control/${caseId}`;
    case "exam":
      return `/exam/${caseId}`;
    default:
      return `/consultation/${caseId}`;
  }
}

export default function CaseSelect() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const rawMethod = params.get("method") as MethodId | null;
  const method: MethodId =
    rawMethod && ["multi_agent", "control", "exam"].includes(rawMethod)
      ? rawMethod
      : "multi_agent";

  useEffect(() => {
    api.cases
      .list()
      .then(setCases)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-500">加载病例列表...</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-semibold text-white ${METHOD_BADGE_BG[method]}`}
            >
              {METHOD_LABELS[method]}
            </span>
          </div>
          <h2 className="text-2xl font-bold text-slate-800">选择训练病例</h2>
          <p className="text-slate-500 mt-1 text-sm">
            选择一个病例开始 {METHOD_LABELS[method]}。难度从基础到挑战递增。
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate("/")}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            返回主页
          </button>
          <button
            onClick={() => navigate("/dashboard")}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            学习数据
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {cases.map((c) => (
          <button
            key={c.case_id}
            onClick={() => navigate(getRouteForCase(method, c.case_id))}
            className="bg-white rounded-xl border border-slate-200 p-6 text-left hover:border-medical hover:shadow-lg transition-all group"
          >
            <div className="flex items-center justify-between mb-3">
              <span
                className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                  difficultyColors[c.difficulty] || difficultyColors[2]
                }`}
              >
                {difficultyLabels[c.difficulty] || "中等"}
              </span>
              <span className="text-xs text-slate-400">
                {c.patient_gender} / {c.patient_age}岁
              </span>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <span className="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center text-slate-600 font-medium">
                {c.patient_name.charAt(0)}
              </span>
              <div>
                <span className="text-sm font-medium text-slate-700">
                  {c.patient_name}
                </span>
                {c.patient_occupation && (
                  <span className="text-xs text-slate-400 ml-1.5">
                    {c.patient_occupation}
                  </span>
                )}
              </div>
            </div>

            <p className="text-sm text-slate-600 leading-relaxed group-hover:text-medical transition-colors">
              "{c.chief_complaint}"
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
