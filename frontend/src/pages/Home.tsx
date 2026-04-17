import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, MethodInfo, MethodId, UserResponse } from "../services/api";

interface Props {
  user: UserResponse;
}

const METHOD_ROUTES: Record<MethodId, string> = {
  multi_agent: "/cases?method=multi_agent",
  single_agent: "/cases?method=single_agent",
  control: "/cases?method=control",
  exam: "/cases?method=exam",
  post_test: "/post-test",
};

const METHOD_ACCENTS: Record<MethodId, string> = {
  multi_agent: "from-blue-50 to-blue-100 border-blue-200",
  single_agent: "from-sky-50 to-sky-100 border-sky-200",
  control: "from-emerald-50 to-emerald-100 border-emerald-200",
  exam: "from-amber-50 to-amber-100 border-amber-200",
  post_test: "from-purple-50 to-purple-100 border-purple-200",
};

const METHOD_BADGE: Record<MethodId, string> = {
  multi_agent: "bg-blue-600 text-white",
  single_agent: "bg-sky-600 text-white",
  control: "bg-emerald-600 text-white",
  exam: "bg-amber-600 text-white",
  post_test: "bg-purple-600 text-white",
};

export default function Home({ user }: Props) {
  const [methods, setMethods] = useState<MethodInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.methods
      .list()
      .then(setMethods)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const isResearcher = user.role === "teacher" || user.role === "researcher";

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <div className="mb-10">
        <h2 className="text-3xl font-bold text-slate-800">
          欢迎进入 Medu-SPAgent
        </h2>
        <p className="text-slate-500 mt-2 leading-relaxed">
          研究面向 medical education 期刊投稿的标准化病人 (SP) 训练平台。
          目前包含 <strong>单智能体 (SA)</strong> / <strong>多智能体 (MA)</strong> /
          <strong> 对照学习 (CT)</strong> / <strong>考试 (Exam)</strong> 四种学习方法与后测问卷。
        </p>
      </div>

      {loading ? (
        <div className="text-slate-500">加载方法列表...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {methods.map((m) => (
            <button
              key={m.id}
              onClick={() => navigate(METHOD_ROUTES[m.id])}
              className={`text-left p-6 rounded-2xl border-2 bg-gradient-to-br ${METHOD_ACCENTS[m.id]} hover:shadow-lg hover:-translate-y-0.5 transition-all`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${METHOD_BADGE[m.id]}`}>
                  {m.short}
                </span>
                <span className="text-xs text-slate-500">
                  {m.needs_case ? "需要选择病例" : "无需病例"}
                </span>
              </div>
              <h3 className="text-xl font-semibold text-slate-800 mb-2">
                {m.name}
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed">{m.description}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                {m.shows_evaluation && (
                  <span className="px-2 py-0.5 bg-white/60 rounded">实时评估</span>
                )}
                {m.shows_tutor && (
                  <span className="px-2 py-0.5 bg-white/60 rounded">导师提示</span>
                )}
                {m.uses_ws && (
                  <span className="px-2 py-0.5 bg-white/60 rounded">实时对话</span>
                )}
                {!m.uses_ws && m.needs_case && (
                  <span className="px-2 py-0.5 bg-white/60 rounded">阶段式表单</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="mt-10 flex flex-wrap gap-3">
        <button
          onClick={() => navigate("/dashboard")}
          className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
        >
          查看学习数据
        </button>
        {isResearcher && (
          <button
            onClick={() => navigate("/admin/prompts")}
            className="px-4 py-2 border border-purple-200 text-purple-700 rounded-lg text-sm hover:bg-purple-50 transition-colors"
          >
            管理 Prompt 库
          </button>
        )}
      </div>
    </div>
  );
}
