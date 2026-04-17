import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
} from "recharts";
import {
  api,
  UserResponse,
  SessionResponse,
  LearningCurvePoint,
  ChecklistHeatmapItem,
} from "../services/api";
import ScoreChart from "../components/ScoreChart";

interface Props {
  user: UserResponse;
}

export default function Dashboard({ user }: Props) {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [learningCurve, setLearningCurve] = useState<LearningCurvePoint[]>([]);
  const [heatmap, setHeatmap] = useState<ChecklistHeatmapItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const sessionsData = await api.sessions.list();
        setSessions(sessionsData);

        const curveData = await api.analytics.learningCurve(user.id);
        setLearningCurve(curveData);

        if (user.role !== "student") {
          const heatmapData = await api.analytics.checklistHeatmap();
          setHeatmap(heatmapData);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [user]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-500">加载数据...</div>
      </div>
    );
  }

  // Aggregate stats
  const completedSessions = sessions.filter((s) => s.final_score !== null);
  const avgScore =
    completedSessions.length > 0
      ? completedSessions.reduce((sum, s) => sum + (s.final_score || 0), 0) /
        completedSessions.length
      : 0;
  const totalTrainingTime = completedSessions.reduce((sum, s) => {
    if (s.ended_at && s.started_at) {
      return (
        sum +
        (new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) /
          1000
      );
    }
    return sum;
  }, 0);

  // Radar data: group heatmap by category
  const categories = new Map<string, { name: string; coverage: number; count: number }>();
  heatmap.forEach((item) => {
    const existing = categories.get(item.category);
    if (existing) {
      existing.coverage += item.coverage_rate;
      existing.count += 1;
    } else {
      categories.set(item.category, {
        name: item.category,
        coverage: item.coverage_rate,
        count: 1,
      });
    }
  });
  const radarData = Array.from(categories.values()).map((c) => ({
    subject: c.name,
    覆盖率: Math.round((c.coverage / c.count) * 100),
    fullMark: 100,
  }));

  // Heatmap bar data
  const barData = heatmap.map((item) => ({
    name:
      item.item_name.length > 8
        ? item.item_name.substring(0, 8) + "..."
        : item.item_name,
    fullName: item.item_name,
    覆盖率: Math.round(item.coverage_rate * 100),
    category: item.category,
  }));

  const handleExportCsv = () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    window.open(
      `${api.analytics.exportCsvUrl()}?token=${token}`,
      "_blank"
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">学习数据看板</h2>
          <p className="text-slate-500 mt-1">追踪你的学习进度和表现趋势</p>
        </div>
        <div className="flex gap-3">
          {user.role !== "student" && (
            <button
              onClick={handleExportCsv}
              className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              导出CSV
            </button>
          )}
          <button
            onClick={() => navigate("/cases")}
            className="px-4 py-2 bg-medical text-white rounded-lg text-sm hover:bg-medical-dark transition-colors"
          >
            开始训练
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-2xl font-bold text-slate-800">
            {completedSessions.length}
          </div>
          <div className="text-sm text-slate-500 mt-1">完成训练次数</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-2xl font-bold text-blue-600">
            {avgScore.toFixed(1)}
          </div>
          <div className="text-sm text-slate-500 mt-1">平均得分</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-2xl font-bold text-green-600">
            {Math.round(totalTrainingTime / 60)}
          </div>
          <div className="text-sm text-slate-500 mt-1">总训练时间(分钟)</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-2xl font-bold text-amber-600">
            {completedSessions.reduce(
              (s, sess) => s + sess.tutor_interventions_count,
              0
            )}
          </div>
          <div className="text-sm text-slate-500 mt-1">导师干预总次数</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Learning Curve */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">
            学习曲线
          </h3>
          <ScoreChart data={learningCurve} />
        </div>

        {/* Radar Chart */}
        {radarData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">
              各维度覆盖率
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fontSize: 11 }}
                  stroke="#94a3b8"
                />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Radar
                  name="覆盖率"
                  dataKey="覆盖率"
                  stroke="#0284c7"
                  fill="#0284c7"
                  fillOpacity={0.2}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Checklist Heatmap */}
      {barData.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">
            Checklist 各项覆盖率
          </h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={barData} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11 }}
                width={80}
              />
              <Tooltip
                formatter={(value: number, name: string, props: any) => [
                  `${value}%`,
                  props.payload.fullName,
                ]}
                contentStyle={{ borderRadius: "12px", fontSize: 13 }}
              />
              <Bar dataKey="覆盖率" fill="#0284c7" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Session History Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">
          训练历史记录
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 px-3 text-slate-500 font-medium">
                  病例
                </th>
                <th className="text-left py-3 px-3 text-slate-500 font-medium">
                  时间
                </th>
                <th className="text-right py-3 px-3 text-slate-500 font-medium">
                  得分
                </th>
                <th className="text-right py-3 px-3 text-slate-500 font-medium">
                  提问数
                </th>
                <th className="text-right py-3 px-3 text-slate-500 font-medium">
                  导师干预
                </th>
                <th className="text-right py-3 px-3 text-slate-500 font-medium">
                  状态
                </th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-slate-100 hover:bg-slate-50"
                >
                  <td className="py-3 px-3 text-slate-700">{s.case_id}</td>
                  <td className="py-3 px-3 text-slate-500">
                    {new Date(s.started_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="py-3 px-3 text-right font-medium">
                    {s.final_score !== null ? s.final_score.toFixed(1) : "-"}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {s.student_messages}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {s.tutor_interventions_count}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {s.ended_at ? (
                      <span className="text-green-600">已完成</span>
                    ) : (
                      <span className="text-amber-500">进行中</span>
                    )}
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="py-8 text-center text-slate-400"
                  >
                    还没有训练记录，快去选择病例开始训练吧
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
