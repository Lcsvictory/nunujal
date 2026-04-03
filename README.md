# NunuJal

Team collaboration web service for university projects.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI
- Database: PostgreSQL

## Structure

- `frontend`: React web app
- `backend`: FastAPI server

## Run

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

Use PostgreSQL and copy `backend/.env.example` to `.env`.

