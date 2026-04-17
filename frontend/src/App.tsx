import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import { useState, useEffect } from "react";
import Login from "./pages/Login";
import Home from "./pages/Home";
import CaseSelect from "./pages/CaseSelect";
import Consultation from "./pages/Consultation";
import ControlLearning from "./pages/ControlLearning";
import Exam from "./pages/Exam";
import PostTest from "./pages/PostTest";
import Dashboard from "./pages/Dashboard";
import PromptAdmin from "./pages/admin/PromptAdmin";
import { api, UserResponse } from "./services/api";

export default function App() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      api.auth
        .me()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem("token");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = (u: UserResponse, token: string) => {
    localStorage.setItem("token", token);
    setUser(u);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-lg text-slate-500">加载中...</div>
      </div>
    );
  }

  const roleLabel = (role: string) =>
    role === "student" ? "学生" : role === "teacher" ? "教师" : "研究员";

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        {user && (
          <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3">
              <div className="w-8 h-8 bg-medical rounded-lg flex items-center justify-center text-white font-bold text-sm">
                SP
              </div>
              <h1 className="text-lg font-semibold text-slate-800">
                Medu-SPAgent · 医学教育 SP 训练平台
              </h1>
            </Link>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-500">
                {user.full_name} ({roleLabel(user.role)})
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-slate-400 hover:text-red-500 transition-colors"
              >
                退出登录
              </button>
            </div>
          </header>
        )}

        <Routes>
          <Route
            path="/login"
            element={user ? <Navigate to="/" /> : <Login onLogin={handleLogin} />}
          />
          <Route
            path="/"
            element={user ? <Home user={user} /> : <Navigate to="/login" />}
          />
          <Route
            path="/cases"
            element={user ? <CaseSelect /> : <Navigate to="/login" />}
          />
          <Route
            path="/consultation/:caseId"
            element={user ? <Consultation user={user} /> : <Navigate to="/login" />}
          />
          <Route
            path="/control/:caseId"
            element={user ? <ControlLearning /> : <Navigate to="/login" />}
          />
          <Route
            path="/exam/:caseId"
            element={user ? <Exam user={user} /> : <Navigate to="/login" />}
          />
          <Route
            path="/post-test"
            element={user ? <PostTest /> : <Navigate to="/login" />}
          />
          <Route
            path="/dashboard"
            element={user ? <Dashboard user={user} /> : <Navigate to="/login" />}
          />
          <Route
            path="/admin/prompts"
            element={user ? <PromptAdmin user={user} /> : <Navigate to="/login" />}
          />
          <Route path="*" element={<Navigate to={user ? "/" : "/login"} />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
