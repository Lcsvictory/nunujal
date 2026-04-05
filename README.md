# NunuJal

Team collaboration web service for university projects.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI
- Database: PostgreSQL

## Structure

- `frontend`: React web app
- `backend`: FastAPI server

## Local Run

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Database

Use PostgreSQL and copy `backend/.env.example` to `backend/.env`.

## Docker Dev Environment

### Why another compose file

`docker-compose.yml` keeps the PostgreSQL-only setup.
`docker-compose.dev.yml` reproduces the actual development environment with:

- `frontend`: Vite dev server with hot reload
- `backend`: FastAPI + Uvicorn reload server
- `postgres`: local development database

This split is better than forcing everything into one Dockerfile because this repository is not a single process app. The frontend, backend, and database have different runtimes and different reload behavior.

### Files added for Docker development

- `frontend/Dockerfile.dev`
- `backend/Dockerfile.dev`
- `docker-compose.dev.yml`
- `backend/.env.example`

### Build and run

1. Start the full development environment.

```bash
docker compose -f docker-compose.dev.yml up --build
```

2. Open the services.

- Frontend: `http://localhost:5073`
- Backend: `http://localhost:8028`
- PostgreSQL: `localhost:5432`

### Stop the environment

```bash
docker compose -f docker-compose.dev.yml down
```

If you also want to remove the database volume:

```bash
docker compose -f docker-compose.dev.yml down -v
```

### Notes

- The dev compose mounts the source code into the containers, so code changes are reflected without rebuilding the image.
- The frontend container uses polling to make file watching stable on Docker Desktop.
- The backend container uses the same FastAPI reload flow as local development.
- Dummy auth-related secrets are baked into `docker-compose.dev.yml` for practice. If you want to run Google login for real, replace them with actual values.
