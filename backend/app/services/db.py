"""
Synchronous database session and helpers for Celery tasks.

Celery workers run synchronous code, so they cannot use the async
sessions. This module provides a sync engine, session factory, and
convenience functions for common DB operations in tasks.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.server import ServerRequest, BuildStep

logger = logging.getLogger(__name__)


def _build_sync_url(async_url: str) -> str:
    """Derive a synchronous DB URL from the async one."""
    url = async_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_sync_url = _build_sync_url(settings.DATABASE_URL)

sync_engine = create_engine(
    _sync_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Context manager that yields a synchronous SQLAlchemy session."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_server_request(session: Session, server_request_id: str) -> dict:
    """Load a ServerRequest and return it as a dict."""
    sr = session.get(ServerRequest, server_request_id)
    if sr is None:
        raise ValueError(f"ServerRequest not found: {server_request_id}")

    return {
        "id": str(sr.id),
        "server_name": sr.server_name,
        "environment": sr.environment,
        "os_type": sr.os_type,
        "instance_size": sr.instance_size,
        "region": sr.region,
        "vpc_id": sr.vpc_id,
        "subnet_id": sr.subnet_id,
        "security_profile": sr.security_profile,
        "domain_join": sr.domain_join,
        "puppet_role": sr.puppet_role,
        "software_packages": sr.software_packages,
        "additional_storage": sr.additional_storage,
        "tags": sr.tags,
        "status": sr.status,
        "status_message": sr.status_message,
        "aws_instance_id": sr.aws_instance_id,
        "private_ip": sr.private_ip,
        "public_ip": sr.public_ip,
        "dns_name": sr.dns_name,
        "awx_host_id": getattr(sr, "awx_host_id", None),
        "puppet_certname": getattr(sr, "puppet_certname", None),
        "puppet_role": sr.puppet_role,
    }


def update_server_status(
    session: Session, server_request_id: str, status: str, **kwargs: Any
) -> None:
    """Update status and optional extra fields on a ServerRequest."""
    sr = session.get(ServerRequest, server_request_id)
    if sr is None:
        logger.error("ServerRequest not found: %s", server_request_id)
        return

    sr.status = status
    for key, value in kwargs.items():
        if hasattr(sr, key):
            setattr(sr, key, value)
    sr.updated_at = datetime.now(timezone.utc)
    logger.info("Updated ServerRequest %s -> status=%s", server_request_id, status)


def update_build_step(
    session: Session, step_id: str, status: str, **kwargs: Any
) -> None:
    """Update status and optional extra fields on a BuildStep."""
    step = session.get(BuildStep, step_id)
    if step is None:
        logger.error("BuildStep not found: %s", step_id)
        return

    step.status = status
    for key, value in kwargs.items():
        if hasattr(step, key):
            setattr(step, key, value)
    step.updated_at = datetime.now(timezone.utc)
    logger.info("Updated BuildStep %s -> status=%s", step_id, status)


def create_build_steps(
    session: Session, server_request_id: str, steps: list[str]
) -> list[dict]:
    """Create BuildStep records for each step in the pipeline."""
    created = []
    for order, step_name in enumerate(steps, start=1):
        step = BuildStep(
            id=uuid4(),
            server_request_id=server_request_id,
            step_name=step_name,
            step_order=order,
            status="pending",
        )
        session.add(step)
        created.append({"id": str(step.id), "step_name": step.step_name})

    session.flush()
    logger.info(
        "Created %d build steps for %s: %s",
        len(steps), server_request_id, steps,
    )
    return created
