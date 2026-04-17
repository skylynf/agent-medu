import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, PromptRow, UserResponse } from "../../services/api";

interface Props {
  user: UserResponse;
}

export default function PromptAdmin({ user }: Props) {
  if (user.role !== "teacher" && user.role !== "researcher") {
    return <Navigate to="/" replace />;
  }
  return <PromptAdminInner />;
}

function PromptAdminInner() {
  const navigate = useNavigate();
  const [keys, setKeys] = useState<string[]>([]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [rows, setRows] = useState<PromptRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draftTemplate, setDraftTemplate] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    api.prompts
      .keys()
      .then((ks) => {
        setKeys(ks);
        if (ks.length > 0) setActiveKey(ks[0]);
      })
      .catch((e) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeKey) return;
    setSuccess(null);
    api.prompts
      .list(activeKey)
      .then((rs) => {
        setRows(rs);
        const active = rs.find((r) => r.active);
        if (active) {
          setDraftTemplate(active.template);
          setDraftNotes(active.notes || "");
        } else if (rs.length > 0) {
          setDraftTemplate(rs[0].template);
          setDraftNotes(rs[0].notes || "");
        }
      })
      .catch((e) => setError(e.message || "加载失败"));
  }, [activeKey]);

  const activeRow = useMemo(() => rows.find((r) => r.active), [rows]);

  const handleSave = async (activate: boolean) => {
    if (!activeKey) return;
    setSaving(true);
    setSuccess(null);
    try {
      const resp = await api.prompts.create({
        key: activeKey,
        template: draftTemplate,
        notes: draftNotes || undefined,
        activate,
      });
      setSuccess(`已保存为 ${resp.version}${activate ? "（已激活）" : ""}`);
      const rs = await api.prompts.list(activeKey);
      setRows(rs);
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (id: string) => {
    setSaving(true);
    setSuccess(null);
    try {
      await api.prompts.activate(id);
      const rs = await api.prompts.list(activeKey || undefined);
      setRows(rs);
      setSuccess("激活成功，下一次推理立即生效");
    } catch (e: any) {
      setError(e.message || "激活失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="max-w-6xl mx-auto px-6 py-10 text-slate-500">加载...</div>;
  }
  if (error) {
    return <div className="max-w-6xl mx-auto px-6 py-10 text-red-600">{error}</div>;
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Prompt 库管理</h2>
          <p className="text-sm text-slate-500 mt-1">
            修改后保存即生成新版本；激活后立即对所有新会话生效（不影响已开始的会话）。
          </p>
        </div>
        <button
          onClick={() => navigate("/")}
          className="px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
        >
          返回主页
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <aside className="col-span-12 md:col-span-3">
          <div className="bg-white border border-slate-200 rounded-xl p-3">
            <div className="text-xs uppercase tracking-wide text-slate-400 px-2 py-1">
              Prompt Keys
            </div>
            <ul className="space-y-1">
              {keys.map((k) => (
                <li key={k}>
                  <button
                    onClick={() => setActiveKey(k)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      activeKey === k
                        ? "bg-medical/10 text-medical font-medium"
                        : "text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {k}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <main className="col-span-12 md:col-span-9 space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-800">{activeKey}</h3>
                <p className="text-xs text-slate-400">
                  当前激活版本: {activeRow ? activeRow.version : "—"}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleSave(false)}
                  disabled={saving}
                  className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50"
                >
                  保存为新草稿
                </button>
                <button
                  onClick={() => handleSave(true)}
                  disabled={saving}
                  className="px-3 py-1.5 text-sm bg-medical text-white rounded-lg hover:bg-medical-dark disabled:opacity-50"
                >
                  保存并激活
                </button>
              </div>
            </div>

            <label className="block text-xs text-slate-500 mb-1">备注（可选）</label>
            <input
              value={draftNotes}
              onChange={(e) => setDraftNotes(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm mb-3"
              placeholder="例如：第二轮迭代，加强共情提示"
            />

            <label className="block text-xs text-slate-500 mb-1">Template</label>
            <textarea
              value={draftTemplate}
              onChange={(e) => setDraftTemplate(e.target.value)}
              rows={20}
              className="w-full font-mono text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical"
            />

            {success && (
              <div className="mt-3 text-sm text-green-600">{success}</div>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-slate-700 mb-3">版本历史</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b">
                    <th className="py-2 pr-3">Version</th>
                    <th className="py-2 pr-3">Active</th>
                    <th className="py-2 pr-3">Created</th>
                    <th className="py-2 pr-3">Notes</th>
                    <th className="py-2 pr-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b last:border-0">
                      <td className="py-2 pr-3 font-mono">{r.version}</td>
                      <td className="py-2 pr-3">
                        {r.active ? (
                          <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                            active
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">inactive</span>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-500">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-500">
                        {r.notes || ""}
                      </td>
                      <td className="py-2 pr-3 text-right">
                        {!r.active && (
                          <button
                            onClick={() => handleActivate(r.id)}
                            className="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-50"
                          >
                            激活
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setDraftTemplate(r.template);
                            setDraftNotes(r.notes || "");
                          }}
                          className="text-xs px-2 py-1 border border-slate-200 rounded ml-2 hover:bg-slate-50"
                        >
                          载入到编辑器
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
