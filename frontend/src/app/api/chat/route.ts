// Claude API를 활용한 PR 컨텍스트 기반 채팅 스트리밍 엔드포인트

import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const SYSTEM_PROMPT = `당신은 Smart PR Inspector라는 AI 에이전트입니다.
GitHub Pull Request 분석을 전문으로 하며, 개발자들이 코드 품질 향상에 집중할 수 있도록 돕습니다.

역할:
- PR 분석 결과를 쉽게 설명
- 컨벤션 위반 사항의 수정 방법 제안
- 테스트 실패 원인 분석 및 해결책 제시
- 영향도 분석 결과 해석
- 머지 가능 여부 종합 판단

말투:
- 한국어로 응답
- 친절하고 전문적으로
- 마크다운 형식 활용
- 핵심을 간결하게 전달`;

export async function POST(req: NextRequest) {
  const { message, context, pr_data } = await req.json();

  const userMessage = `${context ? `[현재 PR 컨텍스트]\n${context}\n\n` : ""}[질문]\n${message}`;

  // 스트리밍 응답 생성
  const stream = await anthropic.messages.stream({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content: userMessage }],
  });

  // ReadableStream으로 변환
  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    async start(controller) {
      for await (const chunk of stream) {
        if (
          chunk.type === "content_block_delta" &&
          chunk.delta.type === "text_delta"
        ) {
          controller.enqueue(encoder.encode(chunk.delta.text));
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
