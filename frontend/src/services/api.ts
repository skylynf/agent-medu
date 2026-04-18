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
  method: string;
  started_at: string;
  ended_at: string | null;
  total_messages: number;
  student_messages: number;
  tutor_interventions_count: number;
  final_score: number | null;
  checklist_json: Record<string, any> | null;
  prompt_versions_json?: Record<string, any> | null;
  worksheet_json?: Record<string, any> | null;
}

export interface WorksheetData {
  chief_complaint?: string;
  hpi?: string;
  past_history?: string;
  physical_exam?: string;
  differentials?: string;
  diagnosis?: string;
  diagnostic_reasoning?: string;
  investigations?: string;
  management?: string;
  _updated_at?: string;
}

export interface WorksheetResponse {
  session_id: string;
  method: string;
  case_id: string;
  fields: string[];
  worksheet: WorksheetData;
}

export interface LearningCurvePoint {
  session_index: number;
  case_id: string;
  method: string;
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

export type MethodId =
  | "multi_agent"
  | "single_agent"
  | "control"
  | "exam"
  | "post_test";

export interface MethodInfo {
  id: MethodId;
  name: string;
  short: string;
  description: string;
  interactive: boolean;
  uses_ws: boolean;
  shows_evaluation: boolean;
  shows_tutor: boolean;
  needs_case: boolean;
}

export interface ControlStage {
  stage_index: number;
  title: string;
  disclosed_content: string;
  prompt_to_student: string | null;
  requires_input: boolean;
  total_stages: number;
  is_final: boolean;
}

export interface ControlStartResponse {
  session_id: string;
  case_id: string;
  method: "control";
  total_stages: number;
  current_stage: ControlStage;
}

export interface ControlSubmitResponse {
  completed: boolean;
  next_stage: ControlStage | null;
  session_id: string;
}

export interface ControlStateResponse {
  session_id: string;
  method: "control";
  case_id: string;
  total_stages: number;
  next_stage_index: number;
  completed: boolean;
  current_stage: ControlStage | null;
}

export interface FinalEvaluation {
  session_id: string;
  method: string;
  case_id: string;
  checklist_results: Record<string, boolean>;
  holistic_scores: {
    history_completeness: number;
    communication: number;
    clinical_reasoning: number;
    diagnostic_accuracy: number;
  };
  diagnosis_given: string | null;
  diagnosis_correct: boolean;
  differentials_given: string[];
  strengths: string[];
  improvements: string[];
  narrative_feedback: string;
  prompt_version: string | null;
  created_at: string | null;
}

export interface SurveyItem {
  id: string;
  text: string;
  reverse?: boolean;
  placeholder?: string;
  /** 主观题等：是否必填 */
  required?: boolean;
}

export interface SurveyInstrument {
  instrument: string;
  display_name: string;
  description?: string;
  scale?: {
    type: string;
    min: number;
    max: number;
    labels: Record<string, string>;
  };
  items: SurveyItem[];
}

export interface PromptRow {
  id: string;
  key: string;
  version: string;
  active: boolean;
  notes: string | null;
  template: string;
  updated_by: string | null;
  created_at: string | null;
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

  methods: {
    list: () => request<MethodInfo[]>("/methods"),
  },

  sessions: {
    list: () => request<SessionResponse[]>("/sessions"),
    get: (sessionId: string) => request<SessionResponse>(`/sessions/${sessionId}`),
    messages: (sessionId: string) => request<any[]>(`/sessions/${sessionId}/messages`),
    finalEvaluation: (sessionId: string) =>
      request<FinalEvaluation>(`/sessions/${sessionId}/final-evaluation`),
    getWorksheet: (sessionId: string) =>
      request<WorksheetResponse>(`/sessions/${sessionId}/worksheet`),
    saveWorksheet: (sessionId: string, worksheet: WorksheetData) =>
      request<{ session_id: string; worksheet: WorksheetData }>(
        `/sessions/${sessionId}/worksheet`,
        { method: "PUT", body: JSON.stringify({ worksheet }) }
      ),
  },

  control: {
    start: (caseId: string) =>
      request<ControlStartResponse>("/sessions/control/start", {
        method: "POST",
        body: JSON.stringify({ case_id: caseId }),
      }),
    state: (sessionId: string) =>
      request<ControlStateResponse>(`/sessions/control/${sessionId}/state`),
    submit: (sessionId: string, stageIndex: number, studentInput: string) =>
      request<ControlSubmitResponse>(`/sessions/control/${sessionId}/submit`, {
        method: "POST",
        body: JSON.stringify({ stage_index: stageIndex, student_input: studentInput }),
      }),
    steps: (sessionId: string) => request<any>(`/sessions/control/${sessionId}/steps`),
  },

  surveys: {
    instruments: () => request<SurveyInstrument[]>("/surveys/instruments"),
    instrument: (instrument: string) =>
      request<SurveyInstrument>(`/surveys/instruments/${instrument}`),
    submit: (data: {
      instrument: string;
      related_session_id?: string | null;
      responses: Record<string, any>;
    }) => request<any>("/surveys", { method: "POST", body: JSON.stringify(data) }),
    mine: () => request<any[]>("/surveys/mine"),
  },

  prompts: {
    keys: () => request<string[]>("/admin/prompts/keys"),
    list: (key?: string) =>
      request<PromptRow[]>(`/admin/prompts${key ? `?key=${encodeURIComponent(key)}` : ""}`),
    active: () => request<{ key: string; version: string; template: string; id: string }[]>(
      "/admin/prompts/active"
    ),
    create: (payload: { key: string; template: string; notes?: string; activate?: boolean }) =>
      request<any>("/admin/prompts", { method: "POST", body: JSON.stringify(payload) }),
    activate: (id: string) =>
      request<any>(`/admin/prompts/${id}/activate`, { method: "POST" }),
    reload: () => request<any>("/admin/prompts/reload", { method: "POST" }),
  },

  analytics: {
    sessions: () => request<any[]>("/analytics/sessions"),
    timeline: (sessionId: string) => request<any[]>(`/analytics/sessions/${sessionId}/timeline`),
    learningCurve: (userId: string) =>
      request<LearningCurvePoint[]>(`/analytics/learning-curve?user_id=${userId}`),
    checklistHeatmap: () => request<ChecklistHeatmapItem[]>("/analytics/checklist-heatmap"),
    tutorInterventions: () => request<any[]>("/analytics/tutor-interventions"),
    exportCsvUrl: () => `${API_BASE}/analytics/export/csv`,
    exportSessionsCsvUrl: () => `${API_BASE}/analytics/export/sessions.csv`,
    exportMessagesJsonlUrl: () => `${API_BASE}/analytics/export/messages.jsonl`,
    exportChecklistMatrixUrl: () => `${API_BASE}/analytics/export/checklist_matrix.csv`,
    exportSurveysCsvUrl: () => `${API_BASE}/analytics/export/surveys.csv`,
    exportCtStepsJsonlUrl: () => `${API_BASE}/analytics/export/ct_steps.jsonl`,
  },
};
