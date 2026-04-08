"use client";

import { motion } from "framer-motion";
import {
  Download,
  Code2,
  TestTube2,
  Play,
  GitFork,
  BookOpen,
  FileText,
  MessageSquare,
  Bell,
  Check,
  X,
  Loader2,
  AlertCircle,
  Minus,
} from "lucide-react";
import { useAppStore } from "@/store";
import type { NodeStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const WORKFLOW_NODES = [
  {
    id: "fetch",
    label: "PR 수집",
    icon: Download,
    description: "GitHub에서 PR diff 및 메타데이터 수집",
    color: "from-blue-600 to-blue-700",
  },
  {
    id: "parallel_start",
    label: null, // 분기점
    type: "fork",
    branches: ["convention", "test_gen"],
  },
  {
    id: "convention",
    label: "컨벤션 검사",
    icon: Code2,
    description: "AST + LLM 하이브리드 컨벤션 검증",
    color: "from-violet-600 to-violet-700",
    branch: "left",
  },
  {
    id: "test_gen",
    label: "테스트 생성",
    icon: TestTube2,
    description: "Claude AI로 pytest 코드 자동 생성",
    color: "from-cyan-600 to-cyan-700",
    branch: "right",
  },
  {
    id: "test_run",
    label: "테스트 실행",
    icon: Play,
    description: "Docker 격리 환경 pytest 실행 (최대 3회 재시도)",
    color: "from-teal-600 to-teal-700",
  },
  {
    id: "impact",
    label: "영향도 분석",
    icon: GitFork,
    description: "AST 정적 분석으로 의존성 추적",
    color: "from-orange-600 to-orange-700",
  },
  {
    id: "domain_explain",
    label: "도메인 설명",
    icon: BookOpen,
    description: "RAG 기반 비즈니스 영향도 생성",
    color: "from-pink-600 to-pink-700",
  },
  {
    id: "doc_sync",
    label: "문서 동기화",
    icon: FileText,
    description: "Swagger/README 업데이트 감지",
    color: "from-amber-600 to-amber-700",
  },
  {
    id: "comment",
    label: "코멘트 작성",
    icon: MessageSquare,
    description: "GitHub PR에 분석 결과 코멘트 게시",
    color: "from-green-600 to-green-700",
  },
  {
    id: "slack",
    label: "Slack 알림",
    icon: Bell,
    description: "인터랙티브 Slack 메시지 전송",
    color: "from-purple-600 to-purple-700",
  },
];

const STATUS_ICON = {
  pending: <Minus className="w-3 h-3 text-gray-500" />,
  running: <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />,
  success: <Check className="w-3 h-3 text-emerald-400" />,
  failed: <X className="w-3 h-3 text-red-400" />,
  skipped: <Minus className="w-3 h-3 text-gray-600" />,
};

const STATUS_RING: Record<NodeStatus, string> = {
  pending: "border-gray-600",
  running: "border-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.5)]",
  success: "border-emerald-400",
  failed: "border-red-400",
  skipped: "border-gray-700",
};

const STATUS_BG: Record<NodeStatus, string> = {
  pending: "bg-gray-800/50",
  running: "bg-blue-500/10",
  success: "bg-emerald-500/10",
  failed: "bg-red-500/10",
  skipped: "bg-gray-800/20",
};

export function AgentWorkflow() {
  const { currentAnalysis, isAnalyzing } = useAppStore();
  const nodeStatus = currentAnalysis?.node_status;

  const getStatus = (nodeId: string): NodeStatus => {
    if (!nodeStatus) return "pending";
    return (nodeStatus as any)[nodeId] ?? "pending";
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center gap-3">
        <h2 className="text-sm font-semibold">Agent 워크플로우</h2>
        {isAnalyzing && (
          <div className="flex items-center gap-1.5 text-[10px] text-blue-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            실행 중
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex flex-col items-center gap-2 max-w-sm mx-auto">
          {WORKFLOW_NODES.map((node, idx) => {
            if ("type" in node && node.type === "fork") {
              return (
                <ForkIndicator key="fork" />
              );
            }

            const status = getStatus(node.id);
            const NodeIcon = (node as any).icon;

            return (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="w-full"
              >
                <div
                  className={cn(
                    "flex items-center gap-3 rounded-xl border p-3 transition-all",
                    STATUS_BG[status],
                    STATUS_RING[status]
                  )}
                >
                  {/* 아이콘 */}
                  <div
                    className={cn(
                      "w-9 h-9 rounded-lg bg-gradient-to-br flex items-center justify-center shrink-0",
                      (node as any).color,
                      status === "pending" || status === "skipped"
                        ? "opacity-40"
                        : "opacity-100"
                    )}
                  >
                    {NodeIcon && <NodeIcon className="w-4 h-4 text-white" />}
                  </div>

                  {/* 텍스트 */}
                  <div className="flex-1 min-w-0">
                    <p
                      className={cn(
                        "text-xs font-medium",
                        status === "pending" || status === "skipped"
                          ? "text-muted-foreground"
                          : "text-foreground"
                      )}
                    >
                      {(node as any).label}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {(node as any).description}
                    </p>
                  </div>

                  {/* 상태 아이콘 */}
                  <div className="shrink-0">{STATUS_ICON[status]}</div>
                </div>

                {/* 연결선 (마지막 제외) */}
                {idx < WORKFLOW_NODES.length - 1 && !("type" in WORKFLOW_NODES[idx + 1]) && (
                  <div className="flex justify-center my-1">
                    <motion.div
                      className={cn(
                        "w-px h-4",
                        status === "success"
                          ? "bg-gradient-to-b from-emerald-400/50 to-border"
                          : "bg-border"
                      )}
                    />
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ForkIndicator() {
  return (
    <div className="w-full flex items-center gap-2 py-1">
      <div className="flex-1 h-px bg-border" />
      <div className="text-[10px] text-muted-foreground px-2 py-0.5 rounded bg-muted border border-border">
        병렬 실행
      </div>
      <div className="flex-1 h-px bg-border" />
    </div>
  );
}
