import { useState } from "react";
import { api, UserResponse } from "../services/api";

interface Props {
  onLogin: (user: UserResponse, token: string) => void;
}

export default function Login({ onLogin }: Props) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("student");
  const [institution, setInstitution] = useState("");
  const [grade, setGrade] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingRegister, setPendingRegister] = useState<{ user: UserResponse; token: string } | null>(
    null
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isRegister) {
        const res = await api.auth.register({
          username,
          password,
          full_name: fullName,
          role,
          institution: institution || undefined,
          grade: grade || undefined,
        });
        setPendingRegister({ user: res.user, token: res.access_token });
      } else {
        const res = await api.auth.login({ username, password });
        onLogin(res.user, res.access_token);
      }
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  const confirmRegisterNotice = () => {
    if (!pendingRegister) return;
    onLogin(pendingRegister.user, pendingRegister.token);
    setPendingRegister(null);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-cyan-50">
      {pendingRegister && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="register-research-notice-title"
        >
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <h2
              id="register-research-notice-title"
              className="text-lg font-semibold text-slate-800 mb-3"
            >
              研究参与说明
            </h2>
            <div className="space-y-3 text-sm text-slate-600 leading-relaxed">
              <p>
                本测试为<strong>前瞻性研究测试</strong>，目前仍处于<strong>学术探索阶段</strong>，
                <strong>仅用于学术研究</strong>。您在平台中产生的资料与信息将<strong>不作他用</strong>，
                仅服务于本研究目的下的分析与报告撰写。
              </p>
              <p className="text-slate-700 font-medium">免责声明</p>
              <p>
                本平台提供的 AI 模拟问诊、学习反馈等功能仅供教学与研究场景使用，
                不构成任何医疗建议、诊断或治疗意见。研究团队将按规范处理研究数据，
                但互联网环境存在固有风险，无法对传输与存储的绝对安全作出法律意义上的保证。
              </p>
              <p className="text-slate-700 font-medium">退出研究</p>
              <p>
                您有权<strong>随时自愿退出</strong>本研究：可随时停止使用本系统，不再参与后续环节。
                已收集数据的留存与匿名化使用以研究团队伦理审查方案为准。
              </p>
            </div>
            <button
              type="button"
              onClick={confirmRegisterNotice}
              className="mt-6 w-full py-3 bg-medical text-white rounded-lg font-medium hover:bg-medical-dark transition-colors"
            >
              同意并继续
            </button>
          </div>
        </div>
      )}
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-medical rounded-2xl flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4 shadow-lg">
            SP
          </div>
          <h1 className="text-2xl font-bold text-slate-800">SPAgent</h1>
          <p className="text-slate-500 mt-1">医学教育智能训练系统</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex mb-6 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => setIsRegister(false)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                !isRegister
                  ? "bg-white text-medical shadow-sm"
                  : "text-slate-500"
              }`}
            >
              登录
            </button>
            <button
              onClick={() => setIsRegister(true)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                isRegister
                  ? "bg-white text-medical shadow-sm"
                  : "text-slate-500"
              }`}
            >
              注册
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                required
              />
            </div>

            {isRegister && (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    姓名
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    角色
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                  >
                    <option value="student">医学生</option>
                    <option value="teacher">教师</option>
                    <option value="researcher">研究员</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      学校/机构
                    </label>
                    <input
                      type="text"
                      value={institution}
                      onChange={(e) => setInstitution(e.target.value)}
                      className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      年级
                    </label>
                    <input
                      type="text"
                      value={grade}
                      onChange={(e) => setGrade(e.target.value)}
                      className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all"
                    />
                  </div>
                </div>
              </>
            )}

            {error && (
              <div className="text-red-500 text-sm bg-red-50 p-3 rounded-lg">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-medical text-white rounded-lg font-medium hover:bg-medical-dark transition-colors disabled:opacity-50"
            >
              {loading ? "处理中..." : isRegister ? "注册" : "登录"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
