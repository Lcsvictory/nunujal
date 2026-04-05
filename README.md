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
Set `DATABASE_URL` to your actual PostgreSQL server.

## Docker Dev Environment

### Why another compose file

`docker-compose.dev.yml` reproduces the actual development environment with:

- `frontend`: Vite dev server with hot reload
- `backend`: FastAPI + Uvicorn reload server

This split is better than forcing everything into one Dockerfile because this repository is not a single process app. The frontend and backend have different runtimes and different reload behavior.
The database is intentionally excluded from Docker so the backend can connect to the real PostgreSQL server you are already using.

### Files added for Docker development

- `frontend/Dockerfile.dev`
- `backend/Dockerfile.dev`
- `docker-compose.dev.yml`
- `backend/.env.example`

### Build and run

1. Create the backend environment file.

```bash
copy backend\.env.example backend\.env
```

2. Edit `backend/.env` and set `DATABASE_URL` to your real PostgreSQL server.

If your database is running on the host machine itself, use `host.docker.internal` as the host value inside `DATABASE_URL`.

3. Start the frontend and backend containers.

```bash
docker compose -f docker-compose.dev.yml up --build
```

4. Open the services.

- Frontend: `http://localhost:5073`
- Backend: `http://localhost:8028`

### Stop the environment

```bash
docker compose -f docker-compose.dev.yml down
```

If you also want to remove the frontend container volume cache:

```bash
docker compose -f docker-compose.dev.yml down -v
```

### Notes

- The dev compose mounts the source code into the containers, so code changes are reflected without rebuilding the image.
- The frontend container uses polling to make file watching stable on Docker Desktop.
- The backend container uses the same FastAPI reload flow as local development.
- Backend secrets and DB connection are read from `backend/.env` instead of being hardcoded in the compose file.
