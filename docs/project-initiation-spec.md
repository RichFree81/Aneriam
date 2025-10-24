# Project Initiation Document – SaaS Application

This document defines the initial technology stack, repository structure, and development standards for building the Aneriam SaaS application.

---

## 1. Technology Stack

### Frontend
- **Framework:** Next.js 14+ (React 18, TypeScript)
- **Styling:** Tailwind CSS (design tokens)
- **Components:** shadcn/ui (Radix) or Material UI (wrapped in `/packages/ui`)
- **Data/State:** TanStack Query + Zustand
- **Forms & Validation:** React Hook Form + Zod
- **Charts:** Recharts or Visx
- **Testing:** Playwright (E2E), Vitest (unit)

### Backend
- **Language:** TypeScript (Node 20 LTS)
- **Framework:** NestJS (Fastify)
- **Contracts:** OpenAPI + Zod
- **Real-time:** WebSockets (Socket.IO) + SSE
- **Background Jobs:** BullMQ (Redis)
- **File Handling:** S3 pre-signed URLs + ClamAV Lambda scanning

### Data & Storage
- **Database:** Aurora PostgreSQL Serverless v2 (multi-tenant with RLS)
- **ORM:** Prisma (or Drizzle)
- **Cache/Queues:** ElastiCache Redis + SQS (upgrade to Kafka/MSK later)
- **Search:** Start with Postgres FTS; OpenSearch/Meilisearch later
- **Files:** S3 (versioning + lifecycle policies)

### Identity & Security
- **IdP:** Auth0 (OIDC) or AWS Cognito
- **RBAC/ABAC:** Role + permission tables, enforced at service layer and DB RLS
- **Audit Logging:** Postgres audit table + immutable log in S3
- **Secrets:** AWS Secrets Manager
- **Rate limiting:** Redis token bucket
- **Compliance:** OWASP ASVS L2 baseline

### DevOps & Platform
- **Containers:** Docker (multi-stage, distroless images)
- **Orchestration:** Amazon EKS (2–3 `t4g.medium` nodes initially)
- **Ingress:** ALB with ACM SSL
- **IaC:** Terraform (infra) + Helm (k8s)
- **CI/CD:** GitHub Actions (lint + test + build + deploy + migrate)
- **Environments:** dev, staging, prod
- **Observability:** OpenTelemetry + Prometheus/Grafana/Loki or AWS Managed
- **Error Tracking:** Sentry
- **CDN/Edge:** CloudFront

---

## 2. Repository Structure

```
repo/
  apps/
    web/        # Next.js frontend
    api/        # NestJS backend
    worker/     # BullMQ jobs
  packages/
    ui/         # shared UI components
    auth/       # auth & RBAC utilities
    config/     # eslint/prettier/tsconfig
    types/      # zod schemas & TS types
  infra/
    terraform/  # AWS infrastructure code
    helm/       # Kubernetes manifests/charts
  docs/         # specifications, research, prompts
  .github/workflows/  # CI/CD pipelines
```

---

## 3. Development Standards
- **Linting & Formatting:** ESLint + Prettier
- **Commits:** Conventional commits + commitlint
- **Branching:** Trunk-based, short-lived feature branches
- **Testing:** Vitest (unit), Supertest (API), Playwright (E2E)
- **Monitoring:** SLOs defined for latency, availability, error budgets

---

## 4. Initial Cloud Setup
- **Region:** AWS af-south-1 (Cape Town), DR in eu-west-1
- **Aurora PostgreSQL:** min 0.5–1 ACU, autoscale up
- **Redis:** t4g.small
- **EKS:** 2–3 nodes (t4g.medium)
- **S3:** buckets for uploads + logs (with versioning + lifecycle policies)
- **Budgets:** AWS Budgets + alarms for cost control

---

## 5. Why This Will Scale
- **Durable stack:** React, TypeScript, Postgres, Redis, S3, Kubernetes, OpenAPI, OpenTelemetry
- **Elastic services:** Aurora Serverless, ElastiCache, SQS scale without redesign
- **Portable architecture:** Abstractions for auth, cache, search, and messaging prevent vendor lock-in
- **Growth path:** add Kafka, shard DB, multi-region DR without rewrites
