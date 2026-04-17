import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import Login from "./pages/Login";
import CaseSelect from "./pages/CaseSelect";
import Consultation from "./pages/Consultation";
import Dashboard from "./pages/Dashboard";
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

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        {user && (
          <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-medical rounded-lg flex items-center justify-center text-white font-bold text-sm">
                SP
              </div>
              <h1 className="text-lg font-semibold text-slate-800">
                SPAgent 医学教育训练系统
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-500">
                {user.full_name} ({user.role === "student" ? "学生" : user.role === "teacher" ? "教师" : "研究员"})
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
            element={
              user ? <Navigate to="/cases" /> : <Login onLogin={handleLogin} />
            }
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
            path="/dashboard"
            element={user ? <Dashboard user={user} /> : <Navigate to="/login" />}
          />
          <Route path="*" element={<Navigate to={user ? "/cases" : "/login"} />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
