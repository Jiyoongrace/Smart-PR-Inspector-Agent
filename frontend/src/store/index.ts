// Zustand 전역 상태 관리

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type {
  AgentState,
  ChatMessage,
  NodeExecutionStatus,
  PRListItem,
} from "@/lib/types";

interface AppState {
  // 선택된 PR
  selectedPR: { prNumber: number; repo: string } | null;
  setSelectedPR: (pr: { prNumber: number; repo: string } | null) => void;

  // PR 목록
  prList: PRListItem[];
  addOrUpdatePR: (item: PRListItem) => void;

  // 현재 분석 중인 PR의 상태
  currentAnalysis: AgentState | null;
  setCurrentAnalysis: (state: AgentState | null) => void;
  updateNodeStatus: (status: NodeExecutionStatus) => void;

  // 실시간 분석 중 여부
  isAnalyzing: boolean;
  setIsAnalyzing: (v: boolean) => void;

  // 채팅 메시지
  chatMessages: ChatMessage[];
  addChatMessage: (msg: ChatMessage) => void;
  updateLastMessage: (content: string) => void;
  clearChat: () => void;

  // 사이드바 토글
  isSidebarOpen: boolean;
  toggleSidebar: () => void;

  // 채팅 패널 토글
  isChatOpen: boolean;
  toggleChat: () => void;

  // 활성 탭 (workspace)
  activeTab: "overview" | "convention" | "tests" | "impact" | "docs" | "diff";
  setActiveTab: (tab: AppState["activeTab"]) => void;

  // 레포지토리 입력
  repoInput: string;
  setRepoInput: (v: string) => void;
}

export const useAppStore = create<AppState>()(
  immer((set) => ({
    selectedPR: null,
    setSelectedPR: (pr) =>
      set((state) => {
        state.selectedPR = pr;
        state.currentAnalysis = null;
        state.activeTab = "overview";
      }),

    prList: [
      // 데모 데이터
      {
        pr_number: 1234,
        repo: "acme/backend",
        title: "재고 차감 로직 개선",
        author: "jiyoon",
        status: "completed",
        created_at: new Date(Date.now() - 3600000).toISOString(),
        risk_level: "medium",
      },
      {
        pr_number: 1233,
        repo: "acme/backend",
        title: "사용자 인증 리팩토링",
        author: "devhoon",
        status: "analyzing",
        created_at: new Date(Date.now() - 7200000).toISOString(),
      },
      {
        pr_number: 1232,
        repo: "acme/frontend",
        title: "결제 페이지 UI 개선",
        author: "jiyoon",
        status: "completed",
        created_at: new Date(Date.now() - 86400000).toISOString(),
        risk_level: "low",
      },
    ],
    addOrUpdatePR: (item) =>
      set((state) => {
        const idx = state.prList.findIndex(
          (p) => p.pr_number === item.pr_number && p.repo === item.repo
        );
        if (idx >= 0) {
          state.prList[idx] = item;
        } else {
          state.prList.unshift(item);
        }
      }),

    currentAnalysis: null,
    setCurrentAnalysis: (analysis) =>
      set((state) => {
        state.currentAnalysis = analysis;
      }),
    updateNodeStatus: (status) =>
      set((state) => {
        if (state.currentAnalysis) {
          state.currentAnalysis.node_status = status;
        }
      }),

    isAnalyzing: false,
    setIsAnalyzing: (v) => set((state) => { state.isAnalyzing = v; }),

    chatMessages: [
      {
        id: "welcome",
        role: "agent",
        content: "안녕하세요! **Smart PR Inspector**입니다. 분석하고 싶은 PR 번호와 레포지토리를 알려주세요.",
        timestamp: new Date().toISOString(),
      },
    ],
    addChatMessage: (msg) =>
      set((state) => {
        state.chatMessages.push(msg);
      }),
    updateLastMessage: (content) =>
      set((state) => {
        const last = state.chatMessages[state.chatMessages.length - 1];
        if (last && last.role === "agent") {
          last.content = content;
          last.isStreaming = false;
        }
      }),
    clearChat: () =>
      set((state) => {
        state.chatMessages = [state.chatMessages[0]]; // 환영 메시지 유지
      }),

    isSidebarOpen: true,
    toggleSidebar: () =>
      set((state) => {
        state.isSidebarOpen = !state.isSidebarOpen;
      }),

    isChatOpen: true,
    toggleChat: () =>
      set((state) => {
        state.isChatOpen = !state.isChatOpen;
      }),

    activeTab: "overview",
    setActiveTab: (tab) => set((state) => { state.activeTab = tab; }),

    repoInput: "owner/repo",
    setRepoInput: (v) => set((state) => { state.repoInput = v; }),
  }))
);
