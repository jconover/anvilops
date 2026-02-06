"""Main v1 API router aggregating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.servers import router as servers_router
from app.api.v1.puppet import router as puppet_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.templates import router as templates_router
from app.api.v1.costs import router as costs_router
from app.api.v1.slack import router as slack_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.audit import router as audit_router

api_v1_router = APIRouter()
api_v1_router.include_router(servers_router, prefix="/servers", tags=["servers"])
api_v1_router.include_router(puppet_router, prefix="/puppet", tags=["puppet"])
api_v1_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
api_v1_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_v1_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_v1_router.include_router(slack_router, prefix="/slack", tags=["slack"])
api_v1_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["audit"])
