"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Menu,
  GitBranch,
  Play,
  Loader2,
  Bell,
  ChevronDown,
  ExternalLink,
  Zap,
  MessageSquare,
} from "lucide-react";
import { useAppStore } from "@/store";
import { connectAnalysisStream } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Header() {
  const {
    toggleSidebar,
    toggleChat,
    isChatOpen,
    selectedPR,
    repoInput,
    setRepoInput,
    isAnalyzing,
    setIsAnalyzing,
    setCurrentAnalysis,
    updateNodeStatus,
    addOrUpdatePR,
    addChatMessage,
  } = useAppStore();

  const [prInput, setPrInput] = useState("");
  const [error, setError] = useState("");

  const handleAnalyze = async () => {
    const prNumber = parseInt(prInput);
    if (!repoInput || !prInput || isNaN(prNumber)) {
      setError("레포지토리와 PR 번호를 올바르게 입력하세요");
      return;
    }

    setError("");
    setIsAnalyzing(true);

    // PR 목록에 추가
    addOrUpdatePR({
      pr_number: prNumber,
      repo: repoInput,
      title: `PR #${prNumber}`,
      author: "",
      status: "analyzing",
      created_at: new Date().toISOString(),
    });

    // 분석 시작 시 currentAnalysis를 빈 상태로 초기화 (노드 상태 업데이트가 동작하도록)
    setCurrentAnalysis({
      pr_data: null,
      convention_result: null,
      test_result: null,
      impact_analysis: null,
      domain_explanation: null,
      domain_sources: [],
      doc_updates: null,
      final_comment: null,
      slack_thread_id: null,
      github_comment_id: null,
      node_status: {
        fetch: "pending",
        convention: "pending",
        test_gen: "pending",
        test_run: "pending",
        impact: "pending",
        domain_explain: "pending",
        doc_sync: "pending",
        comment: "pending",
        slack: "pending",
      },
      error_message: null,
      started_at: new Date().toISOString(),
      completed_at: null,
    });

    // Agent 메시지
    addChatMessage({
      id: Date.now().toString(),
      role: "agent",
      content: `🚀 **PR #${prNumber}** (${repoInput}) 분석을 시작합니다...\n\n각 노드가 순서대로 실행됩니다.`,
      timestamp: new Date().toISOString(),
    });

    // SSE 스트리밍으로 실시간 상태 업데이트
    const es = connectAnalysisStream(
      prNumber,
      repoInput,
      (event) => {
        if (event.type === "node_complete") {
          updateNodeStatus(event.status);
        } else if (event.type === "complete") {
          setIsAnalyzing(false);
          // 최종 분석 결과를 store에 저장 → AnalysisResults 패널에 표시
          setCurrentAnalysis(event.state);
          addOrUpdatePR({
            pr_number: prNumber,
            repo: repoInput,
            title: event.state.pr_data?.title ?? `PR #${prNumber}`,
            author: event.state.pr_data?.author ?? "",
            status: "completed",
            created_at: new Date().toISOString(),
            risk_level: event.state.impact_analysis?.risk_level,
          });
          addChatMessage({
            id: Date.now().toString(),
            role: "agent",
            content: `✅ **PR #${prNumber}** 분석 완료! 결과 패널에서 상세 내용을 확인하세요.`,
            timestamp: new Date().toISOString(),
          });
        } else if (event.type === "error") {
          setIsAnalyzing(false);
          addChatMessage({
            id: Date.now().toString(),
            role: "agent",
            content: `❌ 분석 중 오류 발생: ${event.message}`,
            timestamp: new Date().toISOString(),
          });
        }
      },
      () => setIsAnalyzing(false)
    );

    return () => es.close();
  };

  return (
    <header className="h-14 bg-card border-b border-border flex items-center px-4 gap-3 z-10">
      {/* 사이드바 토글 */}
      <button
        onClick={toggleSidebar}
        className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
      >
        <Menu className="w-4 h-4" />
      </button>

      <div className="h-4 w-px bg-border" />

      {/* PR 분석 입력 폼 */}
      <div className="flex items-center gap-2 flex-1 max-w-2xl">
        {/* 레포지토리 */}
        <div className="flex items-center gap-1.5 bg-muted rounded-lg px-3 py-1.5 min-w-[180px]">
          <GitBranch className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <input
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
            placeholder="owner/repo"
            className="bg-transparent text-xs outline-none text-foreground placeholder-muted-foreground w-full font-mono"
          />
        </div>

        {/* PR 번호 */}
        <div className="flex items-center gap-1.5 bg-muted rounded-lg px-3 py-1.5 w-28">
          <span className="text-muted-foreground text-xs font-mono">#</span>
          <input
            value={prInput}
            onChange={(e) => setPrInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="PR 번호"
            type="number"
            className="bg-transparent text-xs outline-none text-foreground placeholder-muted-foreground w-full font-mono"
          />
        </div>

        {/* 분석 실행 버튼 */}
        <button
          onClick={handleAnalyze}
          disabled={isAnalyzing}
          className={cn(
            "flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-all",
            isAnalyzing
              ? "bg-muted text-muted-foreground cursor-not-allowed"
              : "bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-500 hover:to-blue-500 glow-purple"
          )}
        >
          {isAnalyzing ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              분석 중...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" />
              분석 시작
            </>
          )}
        </button>

        {error && (
          <span className="text-red-400 text-xs">{error}</span>
        )}
      </div>

      {/* 우측 액션 */}
      <div className="ml-auto flex items-center gap-2">
        {/* 현재 분석 중인 PR 표시 */}
        {isAnalyzing && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-1.5"
          >
            <Zap className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
            <span className="text-xs text-blue-400 font-medium">Agent 실행 중</span>
          </motion.div>
        )}

        {/* 알림 */}
        <button className="relative p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
          <Bell className="w-4 h-4" />
          <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 bg-primary rounded-full" />
        </button>

        {/* 채팅 패널 토글 */}
        <button
          onClick={toggleChat}
          className={cn(
            "p-1.5 rounded-md transition-colors",
            isChatOpen
              ? "bg-primary/20 text-primary"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          )}
        >
          <MessageSquare className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
