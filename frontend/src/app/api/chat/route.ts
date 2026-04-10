// OpenAI + RAG를 활용한 PR 컨텍스트 기반 채팅 스트리밍 엔드포인트

import OpenAI from "openai";
import { NextRequest } from "next/server";

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SYSTEM_PROMPT = `당신은 Smart PR Inspector라는 AI 에이전트입니다.
GitHub Pull Request 분석을 전문으로 하며, 개발자들이 코드 품질 향상에 집중할 수 있도록 돕습니다.

역할:
- PR 분석 결과를 쉽게 설명
- 컨벤션 위반 사항의 수정 방법 제안
- 테스트 실패 원인 분석 및 해결책 제시
- 영향도 분석 결과 해석
- 머지 가능 여부 종합 판단

중요 규칙:
- 한국어로 응답
- 도메인 문서가 제공되면 반드시 참고하여 답변하고, 답변 마지막에 "📎 참고: [문서명]" 형태로 출처를 밝힐 것
- 도메인 문서 없이 추론한 경우 "(코드 기반 추론)" 이라고 명시
- 마크다운 형식 활용
- 핵심을 간결하게 전달`;

/** 백엔드 RAG 검색 API 호출 */
async function searchRAG(query: string): Promise<{
  documents: string[];
  sources: string[];
  rag_used: boolean;
}> {
  try {
    const res = await fetch(
      `${API_URL}/api/rag/search?query=${encodeURIComponent(query)}&n_results=3`,
      { signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return { documents: [], sources: [], rag_used: false };
    return await res.json();
  } catch {
    return { documents: [], sources: [], rag_used: false };
  }
}

export async function POST(req: NextRequest) {
  const { message, context } = await req.json();

  // RAG 검색 — 사용자 질문으로 도메인 문서 벡터 검색
  const rag = await searchRAG(message);

  // 컨텍스트 조합
  let userMessage = "";

  if (rag.rag_used && rag.documents.length > 0) {
    const ragContext = rag.documents
      .map((doc, i) => `[문서 ${i + 1}: ${rag.sources[i] || "unknown"}]\n${doc}`)
      .join("\n\n---\n\n");
    userMessage += `[RAG 도메인 문서 — 답변 시 반드시 참고]\n${ragContext}\n\n`;
  }

  if (context) {
    userMessage += `[현재 PR 컨텍스트]\n${context}\n\n`;
  }

  userMessage += `[질문]\n${message}`;

  // OpenAI 스트리밍 응답 생성
  const stream = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    max_tokens: 1024,
    stream: true,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userMessage },
    ],
  });

  // ReadableStream으로 변환
  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    async start(controller) {
      for await (const chunk of stream) {
        const text = chunk.choices[0]?.delta?.content ?? "";
        if (text) {
          controller.enqueue(encoder.encode(text));
        }
      }
      controller.close();
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Transfer-Encoding": "chunked",
    },
  });
}
