"use client";

import { motion } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronRight,
  Code2,
  TestTube2,
  GitFork,
  BookOpen,
  FileText,
  Loader2,
  ExternalLink,
  GitMerge,
  ThumbsUp,
} from "lucide-react";
import { useState } from "react";
import axios from "axios";
import { approvePR, mergePR } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { useAppStore } from "@/store";
import { cn, getRiskColor, getRiskLabel, formatDuration } from "@/lib/utils";
import type { ConventionViolation, ScenarioResult } from "@/lib/types";

const SEVERITY_CONFIG = {
  error: {
    icon: <XCircle className="w-3.5 h-3.5 text-red-400" />,
    bg: "bg-red-400/5 border-red-400/20",
    label: "오류",
  },
  warning: {
    icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
    bg: "bg-amber-400/5 border-amber-400/20",
    label: "경고",
  },
  info: {
    icon: <Info className="w-3.5 h-3.5 text-blue-400" />,
    bg: "bg-blue-400/5 border-blue-400/20",
    label: "정보",
  },
};

export function AnalysisResults() {
  const { currentAnalysis, activeTab, setActiveTab, isAnalyzing } = useAppStore();

  if (!currentAnalysis && !isAnalyzing) {
    return <EmptyState />;
  }

  if (isAnalyzing && !currentAnalysis) {
    return <LoadingState />;
  }

  return (
    <div className="h-full flex flex-col">
      {/* 탭 */}
      <div className="flex gap-1 px-4 py-2 border-b border-border overflow-x-auto">
        {[
          { id: "overview", label: "개요" },
          { id: "convention", label: "컨벤션" },
          { id: "tests", label: "테스트" },
          { id: "impact", label: "영향도" },
          { id: "docs", label: "문서" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors",
              activeTab === tab.id
                ? "bg-primary/20 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className="flex-1 overflow-y-auto p-4">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === "overview" && <OverviewTab />}
          {activeTab === "convention" && <ConventionTab />}
          {activeTab === "tests" && <TestsTab />}
          {activeTab === "impact" && <ImpactTab />}
          {activeTab === "docs" && <DocsTab />}
        </motion.div>
      </div>
    </div>
  );
}

function OverviewTab() {
  const { currentAnalysis, selectedPR } = useAppStore();
  const pr = currentAnalysis?.pr_data;
  const convention = currentAnalysis?.convention_result;
  const test = currentAnalysis?.test_result;
  const impact = currentAnalysis?.impact_analysis;

  return (
    <div className="space-y-4">
      {/* PR 정보 */}
      {pr && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-muted-foreground font-mono mb-1">
                {pr.repo} · #{pr.pr_number}
              </p>
              <h3 className="font-semibold text-sm">{pr.title}</h3>
              <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                <span>작성자: <span className="text-foreground">{pr.author}</span></span>
                <span className="font-mono text-[10px]">
                  {pr.head_branch} → {pr.base_branch}
                </span>
                <span>{pr.changed_files.length}개 파일 변경</span>
              </div>
            </div>
            {pr.pr_url && (
              <a
                href={pr.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground p-1.5 rounded-md hover:bg-muted"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>

          {/* 라벨 */}
          {pr.labels.length > 0 && (
            <div className="flex gap-1.5 mt-3 flex-wrap">
              {pr.labels.map((l) => (
                <span
                  key={l}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/20"
                >
                  {l}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 결과 카드 그리드 */}
      <div className="grid grid-cols-2 gap-3">
        <SummaryCard
          icon={<Code2 className="w-4 h-4" />}
          label="컨벤션"
          value={convention?.passed ? "통과" : `위반 ${convention?.violations.length ?? 0}건`}
          status={convention?.passed ? "success" : "failed"}
          detail={convention?.summary}
        />
        <SummaryCard
          icon={<TestTube2 className="w-4 h-4" />}
          label="테스트"
          value={
            test
              ? `${test.passed_tests}/${test.total_tests} 통과`
              : "N/A"
          }
          status={test?.passed ? "success" : test ? "failed" : "pending"}
          detail={test ? formatDuration(test.duration_seconds) : undefined}
        />
        <SummaryCard
          icon={<GitFork className="w-4 h-4" />}
          label="리스크"
          value={impact ? getRiskLabel(impact.risk_level) : "N/A"}
          status={
            impact?.risk_level === "low"
              ? "success"
              : impact?.risk_level === "critical"
              ? "failed"
              : "warning"
          }
          detail={impact ? `${impact.affected_modules.length}개 모듈 영향` : undefined}
        />
        <SummaryCard
          icon={<FileText className="w-4 h-4" />}
          label="문서 동기화"
          value={currentAnalysis?.doc_updates ? "업데이트 필요" : "최신"}
          status={currentAnalysis?.doc_updates ? "warning" : "success"}
        />
      </div>

      {/* 도메인 설명 */}
      {currentAnalysis?.domain_explanation && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-pink-400" />
            <h4 className="text-xs font-semibold">비즈니스 영향도</h4>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {currentAnalysis.domain_explanation}
          </p>
          {currentAnalysis.domain_sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-[10px] text-muted-foreground mb-1.5">참고 문서:</p>
              {currentAnalysis.domain_sources.map((src, i) => (
                <p key={i} className="text-[10px] text-primary">📎 {src}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 최종 코멘트 미리보기 */}
      {currentAnalysis?.final_comment && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h4 className="text-xs font-semibold mb-3">GitHub 코멘트 미리보기</h4>
          <div className="markdown-body text-xs max-h-64 overflow-y-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {currentAnalysis.final_comment}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* PR 액션 버튼 */}
      {currentAnalysis?.pr_data && <PRActionPanel pr={currentAnalysis.pr_data} />}
    </div>
  );
}

function PRActionPanel({ pr }: { pr: NonNullable<import("@/lib/types").AgentState["pr_data"]> }) {
  const [approveLoading, setApproveLoading] = useState(false);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [approveStatus, setApproveStatus] = useState<"idle" | "done" | "error">("idle");
  const [mergeStatus, setMergeStatus] = useState<"idle" | "done" | "error">("idle");
  const [mergeMethod, setMergeMethod] = useState<"merge" | "squash" | "rebase">("squash");
  const [errorMsg, setErrorMsg] = useState("");

  const handleApprove = async () => {
    setApproveLoading(true);
    setErrorMsg("");
    try {
      await approvePR(pr.repo, pr.pr_number);
      setApproveStatus("done");
    } catch (err: unknown) {
      let msg = "승인 실패";
      if (axios.isAxiosError(err)) {
        const detail: string = err.response?.data?.detail ?? err.message;
        // GitHub 정책: 자신의 PR은 자신이 승인 불가
        if (detail.includes("approve your own pull request")) {
          msg = "자신이 작성한 PR은 직접 승인할 수 없습니다. 다른 팀원에게 요청하세요.";
        } else {
          msg = detail;
        }
      }
      setErrorMsg(msg);
      setApproveStatus("error");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleMerge = async () => {
    setMergeLoading(true);
    setErrorMsg("");
    try {
      await mergePR(pr.repo, pr.pr_number, mergeMethod);
      setMergeStatus("done");
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail ?? err.message
        : "머지 실패";
      setErrorMsg(msg);
      setMergeStatus("error");
    } finally {
      setMergeLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h4 className="text-xs font-semibold mb-3">PR 액션</h4>

      <div className="flex items-center gap-2 flex-wrap">
        {/* 승인 버튼 */}
        <button
          onClick={handleApprove}
          disabled={approveLoading || approveStatus === "done"}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
            approveStatus === "done"
              ? "bg-emerald-500/20 text-emerald-400 cursor-default"
              : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50"
          )}
        >
          {approveLoading
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <ThumbsUp className="w-3.5 h-3.5" />
          }
          {approveStatus === "done" ? "승인 완료" : "PR 승인"}
        </button>

        {/* 머지 방식 선택 */}
        <select
          value={mergeMethod}
          onChange={(e) => setMergeMethod(e.target.value as typeof mergeMethod)}
          disabled={mergeStatus === "done"}
          className="bg-muted text-xs text-foreground rounded-lg px-2 py-1.5 outline-none border border-border"
        >
          <option value="squash">Squash Merge</option>
          <option value="merge">Merge Commit</option>
          <option value="rebase">Rebase Merge</option>
        </select>

        {/* 머지 버튼 */}
        <button
          onClick={handleMerge}
          disabled={mergeLoading || mergeStatus === "done"}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
            mergeStatus === "done"
              ? "bg-purple-500/20 text-purple-400 cursor-default"
              : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 disabled:opacity-50"
          )}
        >
          {mergeLoading
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <GitMerge className="w-3.5 h-3.5" />
          }
          {mergeStatus === "done" ? "머지 완료" : "PR 머지"}
        </button>

        {/* GitHub 링크 */}
        {pr.pr_url && (
          <a
            href={pr.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted transition-all ml-auto"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            GitHub에서 보기
          </a>
        )}
      </div>

      {errorMsg && (
        <p className="mt-2 text-[10px] text-red-400">{errorMsg}</p>
      )}
    </div>
  );
}

function ConventionTab() {
  const { currentAnalysis } = useAppStore();
  const result = currentAnalysis?.convention_result;
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!result) {
    return <PlaceholderSection label="컨벤션 분석 결과를 기다리는 중..." />;
  }

  const byFile = result.violations.reduce<Record<string, ConventionViolation[]>>(
    (acc, v) => {
      acc[v.file] = acc[v.file] ? [...acc[v.file], v] : [v];
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-4">
      {/* 요약 */}
      <div className={cn(
        "flex items-center gap-3 p-4 rounded-xl border",
        result.passed
          ? "bg-emerald-500/10 border-emerald-500/20"
          : "bg-red-500/10 border-red-500/20"
      )}>
        {result.passed
          ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          : <XCircle className="w-5 h-5 text-red-400 shrink-0" />
        }
        <div>
          <p className="text-sm font-medium">
            {result.passed ? "컨벤션 모두 통과" : "컨벤션 위반 발견"}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">{result.summary}</p>
        </div>
      </div>

      {/* 파일별 위반 목록 */}
      {Object.entries(byFile).map(([file, violations]) => (
        <div key={file} className="rounded-xl border border-border overflow-hidden">
          <button
            onClick={() => setExpanded(expanded === file ? null : file)}
            className="w-full flex items-center gap-3 p-3 bg-muted/30 hover:bg-muted/50 transition-colors"
          >
            <Code2 className="w-4 h-4 text-muted-foreground shrink-0" />
            <span className="text-xs font-mono text-left flex-1 truncate">{file}</span>
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded-full text-muted-foreground">
              {violations.length}건
            </span>
            {expanded === file
              ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            }
          </button>

          {expanded === file && (
            <div className="p-3 space-y-2">
              {violations.map((v, i) => {
                const cfg = SEVERITY_CONFIG[v.severity];
                return (
                  <div
                    key={i}
                    className={cn("rounded-lg border p-3", cfg.bg)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {cfg.icon}
                      <span className="text-[10px] font-mono text-muted-foreground">
                        Line {v.line}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground font-mono">
                        {v.rule}
                      </span>
                    </div>
                    <p className="text-xs text-foreground">{v.message}</p>
                    {v.suggestion && (
                      <p className="text-[10px] text-muted-foreground mt-1">
                        💡 {v.suggestion}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}

      {result.violations.length === 0 && (
        <div className="text-center py-8 text-muted-foreground text-xs">
          위반 사항이 없습니다 🎉
        </div>
      )}
    </div>
  );
}

function TestsTab() {
  const { currentAnalysis } = useAppStore();
  const result = currentAnalysis?.test_result;

  if (!result) {
    return <PlaceholderSection label="테스트 시나리오를 생성하는 중..." />;
  }

  const isScenarioMode =
    result.verification_mode === "ai_scenario" && result.scenarios?.length > 0;

  if (isScenarioMode) {
    return <ScenarioView result={result} />;
  }

  // 시나리오 없이 통계만 있는 경우 (스킵/오류)
  return (
    <div className="space-y-4">
      <div className={cn(
        "p-4 rounded-xl border",
        result.passed
          ? "bg-emerald-500/10 border-emerald-500/20"
          : "bg-amber-500/10 border-amber-500/20"
      )}>
        <div className="flex items-center gap-3">
          {result.passed
            ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            : <Info className="w-5 h-5 text-amber-400" />
          }
          <p className="text-sm font-medium text-muted-foreground">
            {result.total_tests === 0
              ? "검증할 시나리오가 없습니다 (변경사항이 충분하지 않음)"
              : "검증 결과를 불러오는 중입니다..."}
          </p>
        </div>
      </div>
    </div>
  );
}

const VERDICT_CONFIG = {
  pass: {
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    border: "border-emerald-500/20 bg-emerald-500/5",
    label: "구현됨",
  },
  fail: {
    icon: <XCircle className="w-4 h-4 text-red-400 shrink-0" />,
    badge: "bg-red-500/10 text-red-400 border-red-500/20",
    border: "border-red-500/20 bg-red-500/5",
    label: "미구현",
  },
  unclear: {
    icon: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
    badge: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    border: "border-amber-500/20 bg-amber-500/5",
    label: "판단 불가",
  },
};

const CATEGORY_COLORS: Record<string, string> = {
  기능: "bg-blue-500/10 text-blue-400",
  예외: "bg-red-500/10 text-red-400",
  경계값: "bg-purple-500/10 text-purple-400",
  보안: "bg-orange-500/10 text-orange-400",
};

function ScenarioView({ result }: { result: NonNullable<import("@/lib/types").TestResult> }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const passCount = result.scenarios.filter((r) => r.verdict === "pass").length;
  const failCount = result.scenarios.filter((r) => r.verdict === "fail").length;
  const unclearCount = result.scenarios.filter((r) => r.verdict === "unclear").length;

  return (
    <div className="space-y-4">
      {/* 전체 요약 */}
      <div className={cn(
        "p-4 rounded-xl border",
        result.passed
          ? "bg-emerald-500/10 border-emerald-500/20"
          : "bg-red-500/10 border-red-500/20"
      )}>
        <div className="flex items-center gap-3 mb-3">
          {result.passed
            ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            : <XCircle className="w-5 h-5 text-red-400" />
          }
          <div>
            <p className="text-sm font-medium">
              {result.passed ? "시나리오 검증 통과" : "검증 실패 — 확인이 필요합니다"}
            </p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              AI가 코드 변경을 분석하여 각 시나리오를 검증했습니다
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "구현됨", value: passCount, color: "text-emerald-400" },
            { label: "미구현", value: failCount, color: "text-red-400" },
            { label: "판단불가", value: unclearCount, color: "text-amber-400" },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className={cn("text-xl font-bold", s.color)}>{s.value}</p>
              <p className="text-[10px] text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>

        {result.duration_seconds > 0 && (
          <p className="text-[10px] text-muted-foreground mt-3">
            검증 시간: {formatDuration(result.duration_seconds)}
          </p>
        )}
      </div>

      {/* 시나리오 카드 목록 */}
      <div className="space-y-2">
        {result.scenarios.map((r: ScenarioResult) => {
          const cfg = VERDICT_CONFIG[r.verdict];
          const isOpen = expanded === r.scenario.id;

          return (
            <div
              key={r.scenario.id}
              className={cn("rounded-xl border overflow-hidden", cfg.border)}
            >
              {/* 헤더 — 클릭으로 펼치기 */}
              <button
                onClick={() => setExpanded(isOpen ? null : r.scenario.id)}
                className="w-full flex items-center gap-3 p-3 hover:bg-white/5 transition-colors text-left"
              >
                {cfg.icon}
                <span className="flex-1 text-xs font-medium leading-snug">
                  {r.scenario.title}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  {r.scenario.category && (
                    <span className={cn(
                      "text-[10px] px-2 py-0.5 rounded-full font-medium",
                      CATEGORY_COLORS[r.scenario.category] ?? "bg-muted text-muted-foreground"
                    )}>
                      {r.scenario.category}
                    </span>
                  )}
                  <span className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full border font-medium",
                    cfg.badge
                  )}>
                    {cfg.label}
                  </span>
                  {isOpen
                    ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                    : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                  }
                </div>
              </button>

              {/* 펼쳐진 상세 내용 */}
              {isOpen && (
                <div className="px-4 pb-4 space-y-3 border-t border-border/50">
                  {/* Given / When / Then */}
                  <div className="mt-3 space-y-2">
                    {[
                      { label: "전제 조건", value: r.scenario.given, color: "text-blue-400" },
                      { label: "동작", value: r.scenario.when, color: "text-purple-400" },
                      { label: "기대 결과", value: r.scenario.then, color: "text-emerald-400" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="flex gap-2">
                        <span className={cn("text-[10px] font-semibold shrink-0 w-16 pt-0.5", color)}>
                          {label}
                        </span>
                        <p className="text-xs text-muted-foreground leading-relaxed">{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* AI 판단 근거 */}
                  <div className="rounded-lg bg-muted/30 p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Info className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[10px] text-muted-foreground font-medium">
                        AI 검증 근거
                        {r.confidence > 0 && (
                          <span className="ml-1 opacity-60">(확신도 {r.confidence}%)</span>
                        )}
                      </span>
                    </div>
                    <p className="text-xs text-foreground leading-relaxed">{r.reasoning}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ImpactTab() {
  const { currentAnalysis } = useAppStore();
  const impact = currentAnalysis?.impact_analysis;

  if (!impact) {
    return <PlaceholderSection label="영향도 분석을 기다리는 중..." />;
  }

  return (
    <div className="space-y-4">
      {/* 리스크 레벨 */}
      <div className={cn(
        "flex items-center gap-3 p-4 rounded-xl border",
        getRiskColor(impact.risk_level)
      )}>
        <div className="text-2xl">
          {impact.risk_level === "low" ? "🟢" :
           impact.risk_level === "medium" ? "🟡" :
           impact.risk_level === "high" ? "🟠" : "🔴"}
        </div>
        <div>
          <p className="text-sm font-medium">리스크 레벨: {getRiskLabel(impact.risk_level)}</p>
          <p className="text-xs text-muted-foreground">
            {impact.affected_modules.length}개 모듈 영향 · {impact.changed_functions.length}개 함수 변경
          </p>
        </div>
      </div>

      {/* 변경된 함수 */}
      {impact.changed_functions.length > 0 && (
        <div className="rounded-xl border border-border p-4">
          <h4 className="text-xs font-semibold mb-3">변경된 함수</h4>
          <div className="flex flex-wrap gap-2">
            {impact.changed_functions.map((fn) => (
              <code
                key={fn}
                className="text-[11px] px-2 py-1 bg-muted rounded-lg font-mono text-primary"
              >
                {fn}()
              </code>
            ))}
          </div>
        </div>
      )}

      {/* 영향받는 모듈 */}
      {impact.affected_modules.length > 0 && (
        <div className="rounded-xl border border-border p-4">
          <h4 className="text-xs font-semibold mb-3">
            영향받는 모듈 ({impact.affected_modules.length}개)
          </h4>
          <div className="space-y-2">
            {impact.affected_modules.map((mod, i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-2 rounded-lg bg-muted/30"
              >
                <GitFork className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <code className="text-[11px] font-mono text-foreground truncate block">
                    {mod.module}
                  </code>
                  <span className="text-[10px] text-muted-foreground">
                    {mod.function}() · line {mod.line}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* API 변경 경고 */}
      {impact.has_api_changes && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-400/20 bg-amber-400/5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-amber-400">API 엔드포인트 변경 감지</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Swagger/OpenAPI 문서 업데이트가 필요합니다. "문서" 탭을 확인하세요.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function DocsTab() {
  const { currentAnalysis } = useAppStore();

  if (!currentAnalysis?.doc_updates) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-3" />
        <p className="text-sm font-medium text-emerald-400">문서 동기화 완료</p>
        <p className="text-xs text-muted-foreground mt-1">업데이트가 필요한 문서가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4">
      <div className="markdown-body text-xs">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {currentAnalysis.doc_updates}
        </ReactMarkdown>
      </div>
    </div>
  );
}

// ── 공통 컴포넌트 ────────────────────────────────────────────────

function SummaryCard({
  icon,
  label,
  value,
  status,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  status: "success" | "failed" | "warning" | "pending";
  detail?: string;
}) {
  const statusColors = {
    success: "border-emerald-400/20 bg-emerald-400/5",
    failed: "border-red-400/20 bg-red-400/5",
    warning: "border-amber-400/20 bg-amber-400/5",
    pending: "border-border bg-muted/20",
  };

  const valueColors = {
    success: "text-emerald-400",
    failed: "text-red-400",
    warning: "text-amber-400",
    pending: "text-muted-foreground",
  };

  return (
    <div className={cn("rounded-xl border p-3", statusColors[status])}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-muted-foreground">{icon}</span>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      </div>
      <p className={cn("text-sm font-semibold", valueColors[status])}>{value}</p>
      {detail && <p className="text-[10px] text-muted-foreground mt-0.5">{detail}</p>}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-8">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-primary/20 flex items-center justify-center mb-4">
        <Code2 className="w-8 h-8 text-primary/50" />
      </div>
      <h3 className="text-sm font-medium text-muted-foreground mb-2">
        분석할 PR을 선택하세요
      </h3>
      <p className="text-xs text-muted-foreground max-w-xs">
        좌측에서 PR을 선택하거나, 상단에서 레포지토리와 PR 번호를 입력하여 분석을 시작하세요.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="h-full flex flex-col items-center justify-center">
      <Loader2 className="w-8 h-8 text-primary animate-spin mb-4" />
      <p className="text-sm text-muted-foreground">Agent 분석 중...</p>
    </div>
  );
}

function PlaceholderSection({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-center">
      <div>
        <Loader2 className="w-6 h-6 text-muted-foreground animate-spin mx-auto mb-3" />
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}
