import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { LearningCurvePoint } from "../services/api";

interface Props {
  data: LearningCurvePoint[];
}

export default function ScoreChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        暂无训练数据
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: `第${d.session_index}次`,
    得分: d.score,
    提问数: d.student_messages,
    导师干预: d.tutor_interventions,
    case: d.case_id,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#94a3b8" />
        <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
        <Tooltip
          contentStyle={{
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            fontSize: 13,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="得分"
          stroke="#0284c7"
          strokeWidth={2}
          dot={{ fill: "#0284c7", r: 4 }}
          activeDot={{ r: 6 }}
        />
        <Line
          type="monotone"
          dataKey="导师干预"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={{ fill: "#f59e0b", r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
