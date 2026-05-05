# Aneriam

A modular application with a React+MUI frontend and FastAPI+SQLite backend.

## Prerequisites
- Python 3.10+
- Node.js 18+

## Quick Start

### Backend (FastAPI)

1. Navigate to the backend directory (create it if it doesn't exist yet, or run from root):
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `.\venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://localhost:8000`.
   Docs: `http://localhost:8000/docs`.

### Frontend (React + MUI)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:5173` (or similar).

## Structure
- `frontend/`: Aneriam platform — React + TypeScript SPA. See [`frontend/CLAUDE.md`](frontend/CLAUDE.md).
- `backend/`: Aneriam platform — FastAPI + PostgreSQL API. See [`backend/CLAUDE.md`](backend/CLAUDE.md).
- `app/`: Cost Control MVP — separate FastAPI + SQLite Windows desktop app. See [`app/CLAUDE.md`](app/CLAUDE.md).
- `docs/`: Centralised documentation ([see governance rules](docs/README.md)).
  - `docs/frontend/`: Frontend UI standards and theme documentation.
  - `docs/specs/`: Architecture specifications (portfolio module, field library, etc.).
- `reports/`: AI-generated reports and audits ([temporary artefacts](reports/README.md)).

## Documentation

All project documentation is centralized in the [`/docs`](docs/) directory. See [`/docs/README.md`](docs/README.md) for governance rules and structure.

### Frontend Documentation
- [UI Standards Index](docs/frontend/ui-standards-index.md) — Complete UI standards (Milestones A-F)
- [Theme & Palette](docs/frontend/ui-theme-policy.md) — Theme governance and color system
- [Forms Standards](docs/frontend/forms-standards.md) — Form construction and validation
- [Accessibility](docs/frontend/accessibility.md) — Accessibility guidelines
- [Responsive Patterns](docs/frontend/responsive.md) — Mobile adaptation rules
- [Golden Screens](docs/frontend/golden-screens.md) — Reference pages for testing

