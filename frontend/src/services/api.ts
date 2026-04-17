const API_BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface UserResponse {
  id: string;
  username: string;
  full_name: string;
  role: string;
  institution: string | null;
  grade: string | null;
  consent_given: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface CaseSummary {
  case_id: string;
  chief_complaint: string;
  difficulty: number;
  patient_name: string;
  patient_age: number;
  patient_gender: string;
  patient_occupation: string;
}

export interface SessionResponse {
  id: string;
  user_id: string;
  case_id: string;
  started_at: string;
  ended_at: string | null;
  total_messages: number;
  student_messages: number;
  tutor_interventions_count: number;
  final_score: number | null;
  checklist_json: Record<string, any> | null;
}

export interface LearningCurvePoint {
  session_index: number;
  case_id: string;
  score: number;
  started_at: string;
  student_messages: number;
  tutor_interventions: number;
}

export interface ChecklistHeatmapItem {
  item_name: string;
  category: string;
  coverage_rate: number;
  total_sessions: number;
}

export const api = {
  auth: {
    register: (data: {
      username: string;
      password: string;
      full_name: string;
      role?: string;
      institution?: string;
      grade?: string;
    }) => request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

    login: (data: { username: string; password: string }) =>
      request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

    me: () => request<UserResponse>("/auth/me"),
  },

  cases: {
    list: () => request<CaseSummary[]>("/cases"),
    get: (caseId: string) => request<any>(`/cases/${caseId}`),
  },

  sessions: {
    list: () => request<SessionResponse[]>("/sessions"),
    get: (sessionId: string) => request<SessionResponse>(`/sessions/${sessionId}`),
    messages: (sessionId: string) => request<any[]>(`/sessions/${sessionId}/messages`),
  },

  analytics: {
    sessions: () => request<any[]>("/analytics/sessions"),
    timeline: (sessionId: string) => request<any[]>(`/analytics/sessions/${sessionId}/timeline`),
    learningCurve: (userId: string) => request<LearningCurvePoint[]>(`/analytics/learning-curve?user_id=${userId}`),
    checklistHeatmap: () => request<ChecklistHeatmapItem[]>("/analytics/checklist-heatmap"),
    tutorInterventions: () => request<any[]>("/analytics/tutor-interventions"),
    exportCsvUrl: () => `${API_BASE}/analytics/export/csv`,
  },
};
