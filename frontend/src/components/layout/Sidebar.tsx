"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitPullRequest,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  ChevronRight,
  Search,
  Settings,
  Zap,
  History,
  ExternalLink,
  RefreshCw,
  GitMerge,
  GitBranch,
  Sparkles,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import axios from "axios";
import { useAppStore } from "@/store";
import { fetchHistory, fetchHistoryItem, createPR, type HistoryItem } from "@/lib/api";
import type { PRListItem, RiskLevel, CreatePRResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const RISK_COLORS: Record<RiskLevel, string> = {
  low: "text-emerald-400",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

const STATUS_ICONS = {
  completed: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
  analyzing: <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />,
  not_started: <Clock className="w-3.5 h-3.5 text-gray-500" />,
  failed: <XCircle className="w-3.5 h-3.5 text-red-400" />,
};

export function Sidebar() {
  const { prList, selectedPR, setSelectedPR, setCurrentAnalysis, isSidebarOpen } = useAppStore();
  const [search, setSearch] = useState("");
  const [navItem, setNavItem] = useState<"prs" | "history" | "create" | "settings">("prs");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await fetchHistory(50);
      setHistory(data.items);
    } catch {
      // 백엔드 미실행 시 빈 목록 유지
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (navItem === "history") {
      loadHistory();
    }
  }, [navItem]);

  const handleHistoryClick = async (item: HistoryItem) => {
    try {
      const detail = await fetchHistoryItem(item.id);
      if (detail.analysis) {
        setCurrentAnalysis(detail.analysis);
      }
    } catch {
      // 조회 실패 시 무시
    }
  };

  const filtered = prList.filter(
    (pr) =>
      pr.title.toLowerCase().includes(search.toLowerCase()) ||
      pr.repo.toLowerCase().includes(search.toLowerCase()) ||
      String(pr.pr_number).includes(search)
  );

  if (!isSidebarOpen) return null;

  return (
    <motion.aside
      initial={{ x: -280 }}
      animate={{ x: 0 }}
      exit={{ x: -280 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="w-72 h-full flex flex-col border-r border-border bg-card"
    >
      {/* 로고 */}
      <div className="h-14 flex items-center px-4 border-b border-border gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center glow-purple">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold gradient-text leading-none">PR Inspector</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">AI Agent Platform</p>
        </div>
      </div>

      {/* 네비게이션 탭 */}
      <div className="flex gap-1 p-2 border-b border-border">
        {[
          { id: "prs", icon: <GitPullRequest className="w-4 h-4" />, label: "PRs" },
          { id: "history", icon: <History className="w-4 h-4" />, label: "이력" },
          { id: "create", icon: <GitMerge className="w-4 h-4" />, label: "생성" },
          { id: "settings", icon: <Settings className="w-4 h-4" />, label: "설정" },
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => setNavItem(item.id as typeof navItem)}
            className={cn(
              "flex-1 flex flex-col items-center gap-1 py-1.5 px-2 rounded-md text-[10px] transition-colors",
              navItem === item.id
                ? "bg-primary/20 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>

      {navItem === "prs" && (
        <>
          {/* 검색 */}
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="PR 검색..."
                className="w-full bg-muted rounded-lg pl-8 pr-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-1 focus:ring-primary/50"
              />
            </div>
          </div>

          {/* PR 목록 */}
          <div className="flex-1 overflow-y-auto py-2">
            <p className="px-3 py-1 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              Pull Requests ({filtered.length})
            </p>

            <AnimatePresence>
              {filtered.map((pr) => (
                <PRListItem
                  key={`${pr.repo}-${pr.pr_number}`}
                  pr={pr}
                  isSelected={
                    selectedPR?.prNumber === pr.pr_number &&
                    selectedPR?.repo === pr.repo
                  }
                  onClick={() =>
                    setSelectedPR({ prNumber: pr.pr_number, repo: pr.repo })
                  }
                />
              ))}
            </AnimatePresence>

            {filtered.length === 0 && (
              <div className="px-3 py-8 text-center text-muted-foreground text-xs">
                PR이 없습니다
              </div>
            )}
          </div>
        </>
      )}

      {navItem === "history" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-border flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              분석 이력 ({history.length})
            </span>
            <button
              onClick={loadHistory}
              disabled={historyLoading}
              className="p-1 rounded hover:bg-muted transition-colors text-muted-foreground"
            >
              <RefreshCw className={cn("w-3 h-3", historyLoading && "animate-spin")} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto py-2">
            {historyLoading && (
              <div className="flex justify-center py-8">
                <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
              </div>
            )}
            {!historyLoading && history.length === 0 && (
              <div className="px-3 py-8 text-center text-muted-foreground text-xs">
                분석 이력이 없습니다.<br />PR을 분석하면 여기에 저장됩니다.
              </div>
            )}
            {!historyLoading && history.map((item) => (
              <button
                key={item.id}
                onClick={() => handleHistoryClick(item)}
                className="w-full text-left px-3 py-3 mx-1 rounded-lg hover:bg-muted/50 transition-all"
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 shrink-0">
                    {item.convention_passed && item.test_passed
                      ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      : <XCircle className="w-3.5 h-3.5 text-red-400" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-0.5">
                      <span className="text-[10px] text-muted-foreground font-mono">#{item.pr_number}</span>
                      <span className={cn(
                        "text-[9px] font-medium uppercase",
                        item.risk_level === "low" ? "text-emerald-400" :
                        item.risk_level === "medium" ? "text-amber-400" :
                        item.risk_level === "high" ? "text-orange-400" : "text-red-400"
                      )}>
                        {item.risk_level}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-foreground truncate leading-tight">
                      {item.pr_title || `PR #${item.pr_number}`}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">{item.repo}</p>
                    <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                      <span>컨벤션 {item.convention_passed ? "✅" : "❌"}</span>
                      <span>테스트 {item.test_passed ? "✅" : "❌"}</span>
                      <span className="ml-auto">
                        {item.created_at
                          ? formatDistanceToNow(new Date(item.created_at), { locale: ko, addSuffix: true })
                          : ""}
                      </span>
                    </div>
                  </div>
                  {item.pr_url && (
                    <a
                      href={item.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="shrink-0 mt-0.5 text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {navItem === "create" && <CreatePRPanel />}

      {navItem === "settings" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-border">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              RAG 문서 관리
            </span>
          </div>
          <div className="p-3 space-y-4 overflow-y-auto flex-1">
            <DocUploadSection
              title="팀 코딩 가이드"
              description="팀 컨벤션 규칙 문서를 업로드하면 PR 분석 시 RAG로 활용됩니다"
              endpoint="/api/rag/upload/convention"
              accept=".md,.txt,.yaml,.yml"
            />
            <DocUploadSection
              title="비즈니스 룰북"
              description="도메인/비즈니스 규칙 문서를 업로드하면 영향도 분석에 활용됩니다"
              endpoint="/api/rag/upload/domain"
              accept=".md,.txt"
            />
            <RagStats />
          </div>
        </div>
      )}

      {/* 하단 상태 */}
      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Agent 온라인
          <span className="ml-auto">v1.0.0</span>
        </div>
      </div>
    </motion.aside>
  );
}

function CreatePRPanel() {
  const [repo, setRepo] = useState("");
  const [head, setHead] = useState("");
  const [base, setBase] = useState("main");
  const [draft, setDraft] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CreatePRResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const data = await createPR({ repo, head, base, draft });
      setResult(data);
    } catch (err: unknown) {
      let msg = "PR 생성에 실패했습니다";
      if (axios.isAxiosError(err)) {
        msg = err.response?.data?.detail ?? err.message ?? msg;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto">
      <div className="p-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
            AI PR 자동 생성
          </span>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1">
          커밋 내역을 분석해 PR 제목과 본문을 자동으로 작성합니다
        </p>
      </div>

      <form onSubmit={handleSubmit} className="p-3 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground font-medium">레포지토리</label>
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/repo"
            required
            className="w-full bg-muted rounded-lg px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
            <GitBranch className="w-3 h-3" /> Head 브랜치 (소스)
          </label>
          <input
            value={head}
            onChange={(e) => setHead(e.target.value)}
            placeholder="feature/my-feature"
            required
            className="w-full bg-muted rounded-lg px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
            <GitBranch className="w-3 h-3" /> Base 브랜치 (대상)
          </label>
          <input
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="main"
            required
            className="w-full bg-muted rounded-lg px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={draft}
            onChange={(e) => setDraft(e.target.checked)}
            className="rounded border-border"
          />
          <span className="text-xs text-muted-foreground">Draft PR로 생성</span>
        </label>

        <button
          type="submit"
          disabled={loading || !repo || !head || !base}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-medium transition-all",
            "bg-primary text-primary-foreground hover:bg-primary/90",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {loading ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              AI가 PR 작성 중...
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              PR 생성
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="mx-3 mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <p className="text-[10px] text-red-400">{error}</p>
        </div>
      )}

      {result && (
        <div className="mx-3 mb-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex flex-col gap-2">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className="text-[10px] text-emerald-400 font-medium">PR 생성 완료!</span>
            {result.draft && (
              <span className="ml-auto text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                Draft
              </span>
            )}
          </div>
          <p className="text-xs font-medium text-foreground leading-tight">
            #{result.pr_number} {result.title}
          </p>
          <a
            href={result.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] text-primary hover:underline"
          >
            <ExternalLink className="w-3 h-3" />
            GitHub에서 PR 보기
          </a>
        </div>
      )}
    </div>
  );
}

function PRListItem({
  pr,
  isSelected,
  onClick,
}: {
  pr: PRListItem;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <motion.button
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={onClick}
      className={cn(
        "w-full text-left px-3 py-3 mx-1 rounded-lg transition-all group",
        "hover:bg-muted/50",
        isSelected && "bg-primary/10 border border-primary/30"
      )}
    >
      <div className="flex items-start gap-2">
        <div className="mt-0.5 shrink-0">
          {STATUS_ICONS[pr.status]}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 mb-0.5">
            <span className="text-[10px] text-muted-foreground font-mono">#{pr.pr_number}</span>
            {pr.risk_level && (
              <span className={cn("text-[9px] font-medium uppercase", RISK_COLORS[pr.risk_level])}>
                {pr.risk_level}
              </span>
            )}
          </div>
          <p className="text-xs font-medium text-foreground truncate leading-tight">
            {pr.title}
          </p>
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[10px] text-muted-foreground truncate">{pr.repo}</span>
            <span className="text-[10px] text-muted-foreground ml-auto shrink-0">
              {formatDistanceToNow(new Date(pr.created_at), { locale: ko, addSuffix: true })}
            </span>
          </div>
        </div>
        <ChevronRight
          className={cn(
            "w-3.5 h-3.5 text-muted-foreground shrink-0 mt-1 transition-transform",
            isSelected && "text-primary rotate-90"
          )}
        />
      </div>
    </motion.button>
  );
}

function DocUploadSection({
  title,
  description,
  endpoint,
  accept,
}: {
  title: string;
  description: string;
  endpoint: string;
  accept: string;
}) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setResult(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("team_name", "default");

      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "업로드 실패");
      }

      const data = await resp.json();
      setResult(`${data.filename} — ${data.chunks}개 청크 인덱싱 완료`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "업로드 실패");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div className="rounded-lg border border-border p-3">
      <h4 className="text-xs font-semibold mb-1">{title}</h4>
      <p className="text-[10px] text-muted-foreground mb-2">{description}</p>
      <label
        className={cn(
          "flex items-center justify-center gap-1.5 w-full py-2 rounded-lg text-xs font-medium cursor-pointer transition-all",
          "border border-dashed border-border hover:border-primary/50 hover:bg-primary/5",
          uploading && "opacity-50 cursor-not-allowed"
        )}
      >
        {uploading ? (
          <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 업로드 중...</>
        ) : (
          <><span className="text-base">📄</span> 파일 선택 ({accept})</>
        )}
        <input
          type="file"
          accept={accept}
          onChange={handleUpload}
          disabled={uploading}
          className="hidden"
        />
      </label>
      {result && (
        <p className="mt-2 text-[10px] text-emerald-400">
          <CheckCircle2 className="w-3 h-3 inline mr-1" />{result}
        </p>
      )}
      {error && (
        <p className="mt-2 text-[10px] text-red-400">{error}</p>
      )}
    </div>
  );
}

function RagStats() {
  const [stats, setStats] = useState<{ domain_docs: number; convention_docs: number } | null>(null);

  useEffect(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${API_BASE}/api/rag/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats) return null;

  return (
    <div className="rounded-lg border border-border p-3">
      <h4 className="text-xs font-semibold mb-2">RAG 인덱스 현황</h4>
      <div className="flex gap-3 text-[10px]">
        <div className="flex-1 text-center p-2 rounded bg-muted">
          <div className="text-lg font-bold text-foreground">{stats.convention_docs}</div>
          <div className="text-muted-foreground">코딩 가이드</div>
        </div>
        <div className="flex-1 text-center p-2 rounded bg-muted">
          <div className="text-lg font-bold text-foreground">{stats.domain_docs}</div>
          <div className="text-muted-foreground">비즈니스 룰북</div>
        </div>
      </div>
    </div>
  );
}
