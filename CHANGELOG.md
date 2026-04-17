# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed - 2026-02-12

#### Repository Structure and Documentation Governance Cleanup
- Centralized all documentation under `/docs` with subdirectories:
  - `frontend` — Frontend UI standards and theme documentation
  - `backend` — Backend documentation (placeholder)
  - `architecture` — Architecture decision records (placeholder)
  - `product` — Product specifications (placeholder)
  - `operations` — Operations and deployment docs (placeholder)
  - `process` — Development process and workflows (placeholder)
  - `decisions` — ADRs and technical decisions (placeholder)
  - `archive` — Obsolete documentation
- Moved all frontend documentation from `/frontend/docs` and `/frontend/src/docs` to `/docs/frontend`
- Removed documentation folders from frontend source code (`/frontend/src/docs`)
- Replaced generic Vite boilerplate `frontend/README.md` with project-specific README redirecting to `/docs/frontend/`
- Removed temporary build artifacts (`tsc_*.txt`, `lint_results.txt`)
- Updated `.gitignore` to prevent future temporary artifact commits
- Established permanent documentation governance rules in `/docs/README.md`
- Created `/reports` directory for AI-generated audits and reports
- Removed unused Turborepo configuration (`turbo.json`)
