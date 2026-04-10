"""
Smart PR Inspector Agent — 아키텍처 다이어그램 생성기 (v3)
Jira 제거, HITL/병렬/재시도/Hybrid RAG 반영
"""

import graphviz

dot = graphviz.Digraph("SmartPRInspector", format="png", engine="dot")

dot.attr(
    rankdir="TB",
    bgcolor="#0d1117",
    fontname="Helvetica Neue",
    pad="1.0",
    nodesep="0.55",
    ranksep="0.7",
    dpi="180",
    size="22,28!",
    ratio="compress",
)
dot.attr("node", fontname="Helvetica Neue", fontsize="14", penwidth="2.2", margin="0.15,0.1")
dot.attr("edge", fontname="Helvetica Neue", fontsize="11", penwidth="2.0", arrowsize="0.9")

# ── 색상 ──────────────────────────────────────────────────────
T = "#f0f6fc"
TD = "#0d1117"
C_TRIGGER = "#238636"
C_TOOL = "#1f6feb"
C_LLM = "#d29922"
C_DECISION = "#8b5cf6"
C_HITL = "#f85149"
C_PARALLEL = "#3fb950"
C_EXT = "#58a6ff"
C_EDGE = "#8b949e"
C_OK = "#3fb950"
C_FAIL = "#f85149"

# ── 범례 ──────────────────────────────────────────────────────
with dot.subgraph(name="cluster_legend") as lg:
    lg.attr(
        label='<<B><FONT POINT-SIZE="16" COLOR="#f0f6fc">LEGEND</FONT></B>>',
        labeljust="l", style="rounded,dashed", color="#30363d",
        fontcolor=T, bgcolor="#161b22", margin="20",
    )
    bs = dict(shape="box", style="rounded,filled", width="2.8", height="0.45", fontsize="13")
    lg.node("L1", "🔧  External Tool Node", fillcolor=C_TOOL, fontcolor=T, **bs)
    lg.node("L2", "🤖  LLM Call Node", fillcolor=C_LLM, fontcolor=TD, **bs)
    lg.node("L3", "◇  Branch / Condition", fillcolor=C_DECISION, fontcolor=T, **bs)
    lg.node("L4", "🧑  Human-in-the-Loop", fillcolor=C_HITL, fontcolor=T, **bs)
    lg.node("L5", "⚡  Parallel (Fork / Join)", fillcolor=C_PARALLEL, fontcolor=TD, **bs)
    lg.node("L6", "🌐  External System", fillcolor=C_EXT, fontcolor=T, **bs)
    for a, b in [("L1","L2"),("L2","L3"),("L3","L4"),("L4","L5"),("L5","L6")]:
        lg.edge(a, b, style="invis")

# ── 노드 정의 ─────────────────────────────────────────────────

# 트리거
dot.node("trigger", "⚡  GitHub PR Event\n(opened / synchronized)",
         shape="box", style="rounded,filled,bold", fillcolor=C_TRIGGER, fontcolor=T, width="4.0", height="0.8", fontsize="15")

# Fetch
dot.node("fetch", "🔧  FETCH\nPR 데이터 수집  (GitHub API + Diff)",
         shape="box", style="rounded,filled", fillcolor=C_TOOL, fontcolor=T, width="3.5", height="0.8")

# Fork
dot.node("fork", "⚡  FORK  (병렬 분기)",
         shape="box", style="rounded,filled,bold", fillcolor=C_PARALLEL, fontcolor=TD, width="3.2", height="0.55", fontsize="14")

# Convention (병렬 A)
dot.node("convention", "🤖  CONVENTION  [Branch A]\nAST 정적분석 + RAG 룰 + LLM 검증",
         shape="box", style="rounded,filled", fillcolor=C_LLM, fontcolor=TD, width="3.5", height="0.8")

# Test Gen (병렬 B)
dot.node("test_gen", "🤖  TEST GEN  [Branch B]\nAI BDD 시나리오 생성 (Given/When/Then)",
         shape="box", style="rounded,filled", fillcolor=C_LLM, fontcolor=TD, width="3.5", height="0.8")

# Join
dot.node("join", "⚡  JOIN  (병렬 합류)",
         shape="box", style="rounded,filled,bold", fillcolor=C_PARALLEL, fontcolor=TD, width="3.2", height="0.55", fontsize="14")

# 아키텍처 룰 체크 (마름모)
dot.node("arch_check", "아키텍처\n룰 위반?",
         shape="diamond", style="filled", fillcolor=C_DECISION, fontcolor=T, width="2.2", height="1.3", fontsize="13")

# HITL
dot.node("hitl", "🧑  HITL — 시니어 리뷰어 승인 대기\n(Email / Slack 알림 발송)",
         shape="box", style="rounded,filled,bold", fillcolor=C_HITL, fontcolor=T, width="4.2", height="0.8", fontsize="14")

# HITL 분기
dot.node("hitl_dec", "승인\n여부?",
         shape="diamond", style="filled", fillcolor=C_DECISION, fontcolor=T, width="1.8", height="1.1", fontsize="13")

# PR 반려
dot.node("reject", "🚫  PR 즉시 반려\n(Merge Block + Comment)",
         shape="box", style="rounded,filled,bold", fillcolor="#da3633", fontcolor=T, width="3.5", height="0.7")

# Test Run
dot.node("test_run", "🔧  TEST RUN\n시나리오 평가  (Docker 격리 / LLM)",
         shape="box", style="rounded,filled", fillcolor=C_TOOL, fontcolor=T, width="3.5", height="0.8")

# 테스트 결과 분기
dot.node("test_check", "테스트\n결과?",
         shape="diamond", style="filled", fillcolor=C_DECISION, fontcolor=T, width="2.0", height="1.2", fontsize="13")

# Fix Test
dot.node("fix_test", "🤖  FIX TEST\nLLM 자동 수정  (최대 3회)",
         shape="box", style="rounded,filled", fillcolor=C_LLM, fontcolor=TD, width="3.0", height="0.8")

# Impact
dot.node("impact", "🤖  IMPACT ANALYSIS\nAST 호출그래프 + LLM 비즈니스 영향도",
         shape="box", style="rounded,filled", fillcolor=C_LLM, fontcolor=TD, width="3.5", height="0.8")

# Domain Explain (Hybrid RAG)
dot.node("domain", "🤖  DOMAIN EXPLAIN\nHybrid RAG (Dense+Sparse) + Re-ranking",
         shape="box", style="rounded,filled", fillcolor=C_LLM, fontcolor=TD, width="3.5", height="0.8")

# RAG DB
dot.node("rag_db", "🌐  ChromaDB\nDense + BM25 Sparse\n+ Cross-Encoder Re-rank",
         shape="box", style="rounded,filled", fillcolor=C_EXT, fontcolor=T, width="3.2", height="0.8")

# Doc Sync
dot.node("doc_sync", "🔧  DOC SYNC\nSwagger 변경 감지 + 업데이트 초안",
         shape="box", style="rounded,filled", fillcolor=C_TOOL, fontcolor=T, width="3.5", height="0.8")

# Comment
dot.node("comment", "🔧  COMMENT\nGitHub PR 코멘트  (Markdown 리포트)",
         shape="box", style="rounded,filled", fillcolor=C_TOOL, fontcolor=T, width="3.5", height="0.8")

# Slack
dot.node("slack", "🔧  SLACK NOTIFY\nBlock Kit 메시지  (Approve / Changes)",
         shape="box", style="rounded,filled", fillcolor=C_TOOL, fontcolor=T, width="3.5", height="0.8")

# 종료
dot.node("end", "✅  END\n분석 완료 + DB 이력 저장",
         shape="box", style="rounded,filled,bold", fillcolor=C_TRIGGER, fontcolor=T, width="3.5", height="0.7", fontsize="15")

# ── 엣지 연결 ─────────────────────────────────────────────────

# 시작 → Fetch
dot.edge("trigger", "fetch", color=C_EDGE)

# Fetch → Fork
dot.edge("fetch", "fork", color=C_EDGE)

# 병렬 분기
dot.edge("fork", "convention", label=" Branch A ", fontcolor=C_PARALLEL, color=C_PARALLEL, style="bold")
dot.edge("fork", "test_gen", label=" Branch B ", fontcolor=C_PARALLEL, color=C_PARALLEL, style="bold")

# 병렬 합류
dot.edge("convention", "join", color=C_PARALLEL, style="bold")
dot.edge("test_gen", "join", color=C_PARALLEL, style="bold")

# Join → 아키텍처 룰 체크
dot.edge("join", "arch_check", color=C_EDGE)

# 아키텍처 분기
dot.edge("arch_check", "hitl", label="  위반!", fontcolor=C_FAIL, color=C_FAIL, style="bold,dashed")
dot.edge("arch_check", "test_run", label="  통과 ✓", fontcolor=C_OK, color=C_OK, style="bold")

# HITL
dot.edge("hitl", "hitl_dec", color=C_HITL)
dot.edge("hitl_dec", "test_run", label="  승인 ✓", fontcolor=C_OK, color=C_OK, style="bold")
dot.edge("hitl_dec", "reject", label="  반려 ✗", fontcolor=C_FAIL, color=C_FAIL, style="bold,dashed")
dot.edge("reject", "end", label=" PR Blocked ", fontcolor=C_FAIL, color=C_FAIL, style="dashed")

# 테스트 분기
dot.edge("test_run", "test_check", color=C_EDGE)
dot.edge("test_check", "fix_test", label="  실패\n  (retry < 3)", fontcolor=C_FAIL, color=C_FAIL, style="bold,dashed")
dot.edge("test_check", "impact", label="  성공 ✓", fontcolor=C_OK, color=C_OK, style="bold")
dot.edge("test_check", "impact", label="  실패 (3회 초과)\n  분석 계속 →", fontcolor="#d29922", color="#d29922", style="dashed")

# 재시도 루프 (빨강 파선)
dot.edge("fix_test", "test_run", label="  재시도 루프", fontcolor=C_FAIL, color=C_FAIL, style="bold,dashed", constraint="false")

# 후속 분석
dot.edge("impact", "domain", color=C_EDGE)
dot.edge("domain", "rag_db", label=" Hybrid Query ", fontcolor=C_EXT, color=C_EXT, style="dashed", constraint="false")
dot.edge("rag_db", "domain", label=" Re-ranked Results ", fontcolor=C_EXT, color=C_EXT, style="dashed", constraint="false")
dot.edge("domain", "doc_sync", color=C_EDGE)
dot.edge("doc_sync", "comment", color=C_EDGE)
dot.edge("comment", "slack", color=C_EDGE)
dot.edge("slack", "end", color=C_EDGE)

# 레이아웃 보정
dot.edge("L6", "trigger", style="invis")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("convention")
    s.node("test_gen")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("hitl")
    s.node("test_run")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("reject")
    s.node("hitl_dec")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("fix_test")
    s.node("impact")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("domain")
    s.node("rag_db")

out = "/Users/jiyoon/AI-Agent/Smart-PR-Inspector-Agent/docs/agent-workflow-diagram"
dot.render(out, cleanup=True)
print(f"✅ 다이어그램 생성: {out}.png")
