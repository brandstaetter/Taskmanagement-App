from fastapi import APIRouter

from taskmanagement_app.api.v1.endpoints import admin, auth
from taskmanagement_app.api.v1.endpoints import print as print_endpoint
from taskmanagement_app.api.v1.endpoints import tasks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(print_endpoint.router, prefix="/print", tags=["print"])
