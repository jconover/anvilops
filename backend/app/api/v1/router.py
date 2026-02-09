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
from app.api.v1.regions import router as regions_router
from app.api.v1.scaling import router as scaling_router
from app.api.v1.cmdb import router as cmdb_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.drift import router as drift_router

api_v1_router = APIRouter()
api_v1_router.include_router(servers_router, prefix="/servers", tags=["servers"])
api_v1_router.include_router(puppet_router, prefix="/puppet", tags=["puppet"])
api_v1_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
api_v1_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_v1_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_v1_router.include_router(slack_router, prefix="/slack", tags=["slack"])
api_v1_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_v1_router.include_router(regions_router, prefix="/regions", tags=["regions"])
api_v1_router.include_router(scaling_router, prefix="/scaling", tags=["scaling"])
api_v1_router.include_router(cmdb_router, prefix="/cmdb", tags=["cmdb"])
api_v1_router.include_router(schedules_router, prefix="/schedules", tags=["schedules"])
api_v1_router.include_router(drift_router, prefix="/drift", tags=["drift"])
