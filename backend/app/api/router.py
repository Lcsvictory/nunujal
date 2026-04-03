from fastapi import APIRouter

from app.api.routes import auth
from app.api.routes import db
from app.api.routes import project_join_requests
from app.api.routes import projects

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(db.router, prefix="/db", tags=["db"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    project_join_requests.router,
    prefix="/project-join-requests",
    tags=["project-join-requests"],
)
