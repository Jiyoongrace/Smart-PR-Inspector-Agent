"use client";

import { AnimatePresence } from "framer-motion";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatPanel } from "@/components/layout/ChatPanel";
import { AgentWorkflow } from "@/components/workspace/AgentWorkflow";
import { AnalysisResults } from "@/components/workspace/AnalysisResults";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";

export default function Home() {
  const { isSidebarOpen, isChatOpen } = useAppStore();

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-background">
      {/* 상단 헤더 */}
      <Header />

      {/* 메인 컨텐츠 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 좌측 사이드바 */}
        <AnimatePresence>
          {isSidebarOpen && <Sidebar />}
        </AnimatePresence>

        {/* 중앙 워크스페이스 */}
        <main className="flex-1 flex overflow-hidden">
          {/* Agent 워크플로우 패널 (좌측) */}
          <div className="w-72 border-r border-border overflow-hidden flex flex-col bg-card/50">
            <AgentWorkflow />
          </div>

          {/* 분석 결과 패널 (우측) */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <AnalysisResults />
          </div>
        </main>

        {/* 우측 채팅 패널 */}
        <AnimatePresence>
          {isChatOpen && <ChatPanel />}
        </AnimatePresence>
      </div>
    </div>
  );
}
