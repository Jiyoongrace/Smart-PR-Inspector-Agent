// API 클라이언트 (FastAPI 백엔드 연동)

import axios from "axios";
import type { AgentState, SSEEvent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// PR 분석 수동 트리거
export async function analyzePR(prNumber: number, repo: string) {
  const { data } = await api.post("/api/analyze", null, {
    params: { pr_number: prNumber, repo },
  });
  return data;
}

// 분석 결과 조회
export async function getAnalysisResult(
  repo: string,
  prNumber: number
): Promise<AgentState> {
  const encodedRepo = encodeURIComponent(repo);
  const { data } = await api.get(`/api/result/${encodedRepo}/${prNumber}`);
  return data;
}

// 분석 상태 조회
export async function getAnalysisStatus(repo: string, prNumber: number) {
  const encodedRepo = encodeURIComponent(repo);
  const { data } = await api.get(`/api/status/${encodedRepo}/${prNumber}`);
  return data as { status: "analyzing" | "completed" | "not_started" };
}

// SSE 스트리밍 연결
export function connectAnalysisStream(
  prNumber: number,
  repo: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void
): EventSource {
  const params = new URLSearchParams({
    pr_number: String(prNumber),
    repo,
  });

  const es = new EventSource(`${API_BASE}/api/analyze/stream?${params}`);

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as SSEEvent;
      onEvent(data);

      if (data.type === "done" || data.type === "complete" || data.type === "error") {
        es.close();
      }
    } catch (e) {
      console.error("SSE 파싱 오류:", e);
    }
  };

  if (onError) {
    es.onerror = onError;
  }

  return es;
}

// 분석 이력 목록 조회
export async function fetchHistory(limit = 50) {
  const { data } = await api.get("/api/history", { params: { limit } });
  return data as { items: HistoryItem[]; total: number };
}

// 특정 분석 이력 상세 조회 (분석 결과 포함)
export async function fetchHistoryItem(recordId: number) {
  const { data } = await api.get(`/api/history/${recordId}`);
  return data as HistoryItem & { analysis: AgentState };
}

// 헬스체크
export async function healthCheck() {
  const { data } = await api.get("/health");
  return data;
}

export interface HistoryItem {
  id: number;
  repo: string;
  pr_number: number;
  pr_title: string;
  pr_author: string;
  pr_url: string;
  base_branch: string;
  head_branch: string;
  changed_files_count: number;
  risk_level: string;
  convention_passed: boolean;
  convention_violations: number;
  test_passed: boolean;
  test_total: number;
  test_passed_count: number;
  has_api_changes: boolean;
  created_at: string;
  duration_seconds: number;
  status: string;
}
