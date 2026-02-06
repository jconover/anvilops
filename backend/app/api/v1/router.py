"""Main v1 API router aggregating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.servers import router as servers_router
from app.api.v1.puppet import router as puppet_router
from app.api.v1.compliance import router as compliance_router

api_v1_router = APIRouter()
api_v1_router.include_router(servers_router, prefix="/servers", tags=["servers"])
api_v1_router.include_router(puppet_router, prefix="/puppet", tags=["puppet"])
api_v1_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
