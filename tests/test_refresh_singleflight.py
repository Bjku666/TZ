from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from backend.services import watchlist_service


def test_quote_refresh_reuses_snapshot_while_another_refresh_is_running() -> None:
    watchlist_service.QUOTE_REFRESH_LOCK.acquire()
    try:
        with (
            patch.object(watchlist_service, "load_watchlist", return_value=pd.DataFrame()),
            patch.object(
                watchlist_service,
                "portfolio_snapshot",
                return_value={"positions": [], "accountState": {"totalAssets": 10000}},
            ),
        ):
            response = watchlist_service.refresh_quotes()
    finally:
        watchlist_service.QUOTE_REFRESH_LOCK.release()

    assert response["success"] is True
    assert response["inProgress"] is True
    assert response["isStale"] is True
    assert response["positions"] == []


def test_pool_rebuild_does_not_start_twice() -> None:
    watchlist_service.POOL_REBUILD_LOCK.acquire()
    try:
        with patch.object(watchlist_service, "load_watchlist", return_value=pd.DataFrame()):
            response = watchlist_service.generate_watchlist()
    finally:
        watchlist_service.POOL_REBUILD_LOCK.release()

    assert response["success"] is False
    assert response["inProgress"] is True
