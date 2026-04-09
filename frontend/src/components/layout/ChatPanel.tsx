"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Bot,
  User,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";

export function ChatPanel() {
  const {
    chatMessages,
    addChatMessage,
    isChatOpen,
    toggleChat,
    selectedPR,
    currentAnalysis,
    isAnalyzing,
  } = useAppStore();

  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isThinking) return;

    setInput("");

    // 유저 메시지 추가
    addChatMessage({
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    });

    setIsThinking(true);

    // Agent 응답 생성 (Claude API 호출)
    try {
      const agentMsgId = (Date.now() + 1).toString();
      addChatMessage({
        id: agentMsgId,
        role: "agent",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      });

      // 분석 컨텍스트 포함한 프롬프트 구성
      const context = currentAnalysis
        ? `현재 분석 중인 PR: #${selectedPR?.prNumber} (${selectedPR?.repo})
컨벤션 결과: ${currentAnalysis.convention_result?.passed ? "통과" : "실패"}
테스트 결과: ${currentAnalysis.test_result?.passed ? "통과" : "실패"}
리스크: ${currentAnalysis.impact_analysis?.risk_level ?? "N/A"}`
        : "현재 선택된 PR 없음";

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          context,
          pr_data: currentAnalysis?.pr_data,
        }),
      });

      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          fullText += chunk;

          // 스트리밍 업데이트
          const { updateLastMessage } = useAppStore.getState();
          updateLastMessage(fullText);
        }
      }
    } catch (e) {
      const { updateLastMessage } = useAppStore.getState();
      updateLastMessage("죄송합니다. 응답 생성 중 오류가 발생했습니다.");
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isChatOpen) return null;

  return (
    <motion.aside
      initial={{ x: 360 }}
      animate={{ x: 0 }}
      exit={{ x: 360 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="w-80 h-full flex flex-col border-l border-border bg-card"
    >
      {/* 헤더 */}
      <div className="h-14 flex items-center px-4 border-b border-border gap-3">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold">Agent Chat</p>
          <p className="text-[10px] text-muted-foreground">
            {isAnalyzing ? (
              <span className="text-blue-400 flex items-center gap-1">
                <Loader2 className="w-2.5 h-2.5 animate-spin" /> 분석 실행 중...
              </span>
            ) : (
              "Claude AI 기반 대화"
            )}
          </p>
        </div>
        <button
          onClick={toggleChat}
          className="p-1 rounded-md hover:bg-muted text-muted-foreground"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence initial={false}>
          {chatMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex gap-2",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {msg.role === "agent" && (
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shrink-0 mt-1">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
              )}

              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-3 py-2",
                  msg.role === "user"
                    ? "chat-message-user"
                    : "chat-message-agent"
                )}
              >
                {msg.isStreaming && !msg.content ? (
                  <div className="flex gap-1 py-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                ) : (
                  <div className="markdown-body text-xs">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
                <p className="text-[9px] text-muted-foreground mt-1">
                  {formatDistanceToNow(new Date(msg.timestamp), {
                    locale: ko,
                    addSuffix: true,
                  })}
                </p>
              </div>

              {msg.role === "user" && (
                <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-1">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* 빠른 질문 버튼 */}
      {chatMessages.length <= 2 && (
        <div className="px-4 pb-3 flex flex-wrap gap-1.5">
          {[
            "컨벤션 위반 설명해줘",
            "테스트 실패 원인은?",
            "영향도 요약해줘",
            "머지해도 괜찮아?",
          ].map((q) => (
            <button
              key={q}
              onClick={() => setInput(q)}
              className="text-[10px] px-2.5 py-1 rounded-full bg-muted hover:bg-primary/20 hover:text-primary border border-border hover:border-primary/30 transition-colors text-muted-foreground"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* 입력창 */}
      <div className="p-3 border-t border-border">
        <div className="flex gap-2 items-end">
          <div className="flex-1 bg-muted rounded-xl px-3 py-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Agent에게 질문하세요..."
              rows={1}
              className="w-full bg-transparent text-xs text-foreground placeholder-muted-foreground outline-none resize-none max-h-24"
              style={{ height: "auto" }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
              }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isThinking}
            className={cn(
              "p-2 rounded-xl transition-all shrink-0",
              input.trim() && !isThinking
                ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-500 hover:to-blue-500"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            {isThinking ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        <p className="text-[9px] text-muted-foreground mt-1.5 text-center">
          <Sparkles className="w-2.5 h-2.5 inline mr-1" />
          Enter로 전송
        </p>
      </div>
    </motion.aside>
  );
}
