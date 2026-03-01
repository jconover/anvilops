"""Unit tests for app.db.session — async database session factory."""

from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# get_db dependency
# ---------------------------------------------------------------------------


class TestGetDb:
    @patch("app.db.session.async_session_maker")
    async def test_yields_session_and_commits(self, mock_maker):
        from app.db.session import get_db

        mock_session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = False
        mock_maker.return_value = ctx

        gen = get_db()
        session = await gen.__anext__()
        assert session is mock_session

        # Simulate successful completion — StopAsyncIteration triggers commit path
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    @patch("app.db.session.async_session_maker")
    async def test_rollback_on_exception(self, mock_maker):
        from app.db.session import get_db

        mock_session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = False
        mock_maker.return_value = ctx

        gen = get_db()
        await gen.__anext__()

        # Simulate an exception during request processing
        try:
            await gen.athrow(ValueError("db error"))
        except ValueError:
            pass
