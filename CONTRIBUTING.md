# Digital Campus Unified App

A monorepo scaffold for the Digital Campus project — a unified application combining a Next.js frontend and a FastAPI backend.

## Project Structure

```
New-project/
├── frontend/              # Next.js frontend application
│   ├── components/        # Reusable UI components
│   ├── pages/             # Next.js pages (file-based routing)
│   ├── styles/            # CSS / Tailwind styles
│   └── package.json
├── services/
│   └── backend/           # FastAPI backend application
│       ├── app/
│       │   ├── api/       # API route handlers
│       │   ├── core/      # Config, security, dependencies
│       │   ├── schemas/   # Pydantic models
│       │   └── main.py    # FastAPI entry point
│       └── requirements.txt
├── .github/
│   └── workflows/         # CI/CD pipelines
├── .env.example           # Environment variable template
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### Backend Setup

```bash
cd services/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp ../../.env.example ../../.env  # edit with your values
uvicorn app.main:app --reload --port 8000
```

The API will be available at [http://localhost:8000](http://localhost:8000).
Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

## API Endpoints (POC)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/`      | Health check — returns welcome message |
| GET    | `/docs`  | Auto-generated Swagger UI |

## Tech Stack

- **Backend:** FastAPI, Python 3.10+, Pydantic, Uvicorn
- **Frontend:** Next.js 14, React 18, TypeScript
- **CI/CD:** GitHub Actions (planned)
- **Database:** SQLite (POC) → PostgreSQL (production)

## License

MIT
