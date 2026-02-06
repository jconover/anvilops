"""Main v1 API router aggregating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.servers import router as servers_router

api_v1_router = APIRouter()
api_v1_router.include_router(servers_router, prefix="/servers", tags=["servers"])
