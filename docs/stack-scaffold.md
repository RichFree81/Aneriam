## Aneriam Monorepo Scaffold

### What shipped
- **Workspace tooling:** `pnpm` workspace with `turbo` to orchestrate `build`, `lint`, `test`, and `dev` across apps and packages.
- **Shared config:** `@aneriam/config` centralizes ESLint (React/Node flavors), Prettier, and tsconfig presets; root configs re-export these for consistency.
- **Apps:**  
  - `apps/web` – Next.js 14 (App Router, Tailwind, TypeScript) with a branded landing page consuming `@aneriam/ui`.  
  - `apps/api` – NestJS 10 on Fastify, Vitest for unit tests, ready for RLS-backed multi-tenant services.  
  - `apps/worker` – BullMQ worker skeleton with graceful shutdown and demo seeding.
- **Packages:**  
  - `@aneriam/ui` – First shared component (`Button`) with Radix Slot + Tailwind-friendly styles.  
  - `@aneriam/auth` – Role and permission primitives with Zod validation helpers.  
  - `@aneriam/types` – Example shared domain schemas (project model, paginated response helper).  
  - `@aneriam/config` – See above.
- **Scripts:** `pnpm dev|build|lint|test|format` run through `turbo`; individual apps expose focused scripts (e.g., `pnpm --filter api dev`).
- **Testing:** Vitest baseline in API; ready to extend into Playwright (web) and contract testing later.

### Stack notes & deviations from the spec
- Stuck with the recommended stack but version-pinned packages where upstream releases lag (`@nestjs/schematics@^10.2.3` is the latest v10).
- API defaults to Fastify adapter out of the gate to match scaling goals.
- Jest assets from the Nest CLI template were removed in favor of Vitest (per spec preference for Vitest).
- Root lints/tests flow through shared config rather than per-app settings to avoid drift.
- Worker ships with BullMQ/ioredis but keeps Redis connection details configurable via env to support ElastiCache/SQS piping later.

### Next steps
1. Wire CI (GitHub Actions) for lint/test/build targets and enforce `pnpm install --frozen-lockfile`.
2. Introduce Prisma schema + migrations for the multi-tenant Postgres design.
3. Add API contract tooling (e.g., `@fastify/swagger`, OpenAPI generation, Zod-to-OpenAPI helpers).
4. Flesh out shared UI (tokens, layout primitives) and automate storybook or docs deployment.
5. Provision Terraform + Helm skeletons aligned with AWS/EKS targets from the initiation spec.
