// OpenAI GPT-5.4를 활용한 PR 컨텍스트 기반 채팅 스트리밍 엔드포인트

import OpenAI from "openai";
import { NextRequest } from "next/server";

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
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
  const { message, context } = await req.json();

  const userMessage = `${context ? `[현재 PR 컨텍스트]\n${context}\n\n` : ""}[질문]\n${message}`;

  // OpenAI 스트리밍 응답 생성
  const stream = await openai.chat.completions.create({
    model: "gpt-5.4",
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
