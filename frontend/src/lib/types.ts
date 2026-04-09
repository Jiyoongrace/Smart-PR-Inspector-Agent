// Agent 상태 및 UI 타입 정의

export type NodeStatus = "pending" | "running" | "success" | "failed" | "skipped";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface NodeExecutionStatus {
  fetch: NodeStatus;
  convention: NodeStatus;
  test_gen: NodeStatus;
  test_run: NodeStatus;
  impact: NodeStatus;
  domain_explain: NodeStatus;
  doc_sync: NodeStatus;
  comment: NodeStatus;
  slack: NodeStatus;
}

export interface ConventionViolation {
  file: string;
  line: number;
  rule: string;
  message: string;
  suggestion?: string;
  severity: "error" | "warning" | "info";
}

export interface ConventionResult {
  passed: boolean;
  violations: ConventionViolation[];
  summary: string;
}

export type ScenarioVerdict = "pass" | "fail" | "unclear";

export interface TestScenario {
  id: string;
  title: string;
  given: string;
  when: string;
  then: string;
  category: string;
}

export interface ScenarioResult {
  scenario: TestScenario;
  verdict: ScenarioVerdict;
  reasoning: string;
  confidence: number;
}

export interface TestResult {
  passed: boolean;
  test_code: string;
  stdout: string;
  stderr: string;
  retry_count: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  duration_seconds: number;
  // AI 시나리오 검증 결과
  scenarios: ScenarioResult[];
  verification_mode: "ai_scenario" | "code";
}

export interface BusinessImpact {
  summary: string;
  affected_features: string[];
  user_facing_changes: string;
  risk_description: string;
  recommendations: string[];
}

export interface ImpactAnalysis {
  changed_functions: string[];
  affected_modules: Array<{
    module: string;
    function: string;
    line: number;
    call_chain: string[];
  }>;
  has_api_changes: boolean;
  call_chain: string[];
  risk_level: RiskLevel;
  business_impact?: BusinessImpact;
}

export interface PRData {
  pr_number: number;
  repo: string;
  author: string;
  title: string;
  body: string;
  diff: string;
  changed_files: string[];
  base_branch: string;
  head_branch: string;
  pr_url: string;
  labels: string[];
  linked_issues: number[];
}

export interface AgentState {
  pr_data: PRData | null;
  convention_result: ConventionResult | null;
  test_result: TestResult | null;
  impact_analysis: ImpactAnalysis | null;
  domain_explanation: string | null;
  domain_sources: string[];
  doc_updates: string | null;
  final_comment: string | null;
  slack_thread_id: string | null;
  github_comment_id: number | null;
  node_status: NodeExecutionStatus;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// SSE 이벤트 타입
export type SSEEvent =
  | { type: "start"; pr_number: number; repo: string; timestamp: string }
  | { type: "node_complete"; node: string; status: NodeExecutionStatus; timestamp: string }
  | { type: "complete"; state: AgentState; timestamp: string }
  | { type: "error"; message: string; timestamp: string }
  | { type: "done" };

// UI 상태
export interface PRListItem {
  pr_number: number;
  repo: string;
  title: string;
  author: string;
  status: "analyzing" | "completed" | "not_started" | "failed";
  created_at: string;
  risk_level?: RiskLevel;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

// PR 자동 생성
export interface CreatePRRequest {
  repo: string;
  head: string;
  base: string;
  draft: boolean;
}

export interface CreatePRResult {
  pr_number: number;
  pr_url: string;
  title: string;
  body: string;
  head: string;
  base: string;
  draft: boolean;
}

// 노드 메타데이터 (UI 표시용)
export interface WorkflowNode {
  id: string;
  label: string;
  icon: string;
  description: string;
  status: NodeStatus;
}
