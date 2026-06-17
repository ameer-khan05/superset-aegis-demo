# Aegis — Event-Driven Security Remediation Orchestrator

Aegis automates the remediation of security vulnerabilities found by SonarCloud in the Apache Superset fork. When a scan completes, Aegis catches the webhook, fetches findings, creates GitHub issues, and dispatches Devin AI sessions to fix the code and open PRs.

## Architecture

```
SonarCloud scan → webhook → Aegis (FastAPI)
                                ├── Fetch BLOCKER findings from Sonar API
                                ├── Create GitHub Issues
                                ├── Launch Devin sessions (API)
                                ├── Poll sessions → collect structured output
                                └── Dashboard (executive summary + audit log)
```

## Prerequisites

- Docker & Docker Compose
- ngrok (for webhook exposure during demo)
- API keys (see `.env.example`)

## Quick Start

```bash
# 1. Clone and enter the aegis directory
cd aegis

# 2. Copy and fill in your secrets
cp .env.example .env
# Edit .env with your actual tokens

# 3. Run
docker-compose up --build

# 4. Expose via ngrok (separate terminal)
ngrok http 8000

# 5. Configure the ngrok URL as a webhook in SonarCloud
```

## Simulate (without live SonarCloud)

```bash
# Send a canned webhook payload to trigger the full flow
curl -X POST http://localhost:8000/webhook/sonar \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_webhook.json
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Healthcheck |
| `/webhook/sonar` | POST | SonarCloud webhook receiver |
| `/dashboard` | GET | Executive summary dashboard |
| `/api/results` | GET | Audit log (JSON) |
| `/api/summary` | GET | KPI numbers (JSON) |

## Environment Variables

See `.env.example` for the full list. Key variables:

- `AEGIS_MIN_SEVERITY` — Minimum severity to remediate (default: `BLOCKER`)
- `AEGIS_MAX_ACU` — ACU cap per Devin session (default: `15`)

## Project Structure

```
aegis/
├── app/
│   ├── main.py             # FastAPI entrypoint
│   ├── config.py           # Pydantic Settings
│   ├── models.py           # Domain models
│   ├── routers/
│   │   ├── webhook.py      # POST /webhook/sonar
│   │   └── dashboard.py    # Dashboard + API routes
│   ├── services/
│   │   ├── sonar.py        # SonarCloud API client
│   │   ├── github.py       # GitHub Issues client
│   │   ├── devin.py        # Devin API client
│   │   └── orchestrator.py # Remediation pipeline
│   └── templates/
│       └── dashboard.html  # Jinja2 template (Stage 7)
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```
