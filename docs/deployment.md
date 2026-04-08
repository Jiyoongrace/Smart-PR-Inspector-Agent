# 배포 및 운영

## Docker Compose (로컬/스테이징)

```yaml
# docker-compose.yml 요약
services:
  api:        # FastAPI Webhook 서버 (포트 8000)
  frontend:   # Next.js UI (포트 3000)
  redis:      # 캐시 (포트 6379)
  postgres:   # DB (포트 5432)
  chromadb:   # 벡터 DB (포트 8001)
```

```bash
docker-compose up -d
```

---

## 환경변수

`.env.example` 참조:

```bash
# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...

# LLM
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # 옵션

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# 데이터베이스
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379

# Vector DB
CHROMA_HOST=localhost
CHROMA_PORT=8001
PINECONE_API_KEY=...           # 옵션 (클라우드)

# 앱 설정
APP_ENV=production
LOG_LEVEL=INFO
```

---

## GitHub Actions (CI/CD)

```yaml
# .github/workflows/deploy.yml
name: Deploy Smart PR Inspector

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Railway
        run: railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

---

## GitHub Webhook 설정

1. GitHub 레포 → Settings → Webhooks → Add webhook
2. Payload URL: `https://your-domain.com/webhook/github`
3. Content type: `application/json`
4. Secret: `.env`의 `GITHUB_WEBHOOK_SECRET`과 동일
5. Events: `Pull requests`, `Pull request reviews`

---

## 모니터링

### Prometheus 메트릭
- `pr_analyzed_total`: 분석된 PR 수
- `analysis_duration_seconds`: 분석 소요 시간
- `convention_violations_total`: 컨벤션 위반 수
- `test_pass_rate`: 테스트 통과율

### Sentry 에러 추적
```python
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
```

### 로그 구조
```json
{
  "timestamp": "2026-04-08T10:00:00Z",
  "level": "INFO",
  "pr_number": 1234,
  "node": "convention_check",
  "duration_ms": 1250,
  "violations": 3
}
```

---

## 프로덕션 배포 옵션

| 옵션 | 비용 | 특징 |
|------|------|------|
| **Railway** | $5 크레딧/월 | 간편한 배포, GitHub 연동 |
| **Render** | 무료 (Sleep) | 무료 티어 (15분 비활성 시 슬립) |
| **Fly.io** | 무료 (소규모) | 빠른 콜드 스타트 |
| **Cloudflare Workers** | 무료 (제한적) | Serverless, 글로벌 엣지 |
| **AWS Lambda** | Pay-per-use | 기업 환경 |

---

## 성능 최적화

- **Redis 캐싱**: 동일 PR diff 재분석 방지 (TTL 24시간)
- **비동기 처리**: FastAPI + asyncio로 동시 PR 처리
- **토큰 최적화**: diff > 5000자 시 청킹 처리
- **컨테이너 재사용**: Docker 컨테이너 풀링으로 테스트 실행 가속
