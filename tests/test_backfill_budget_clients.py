from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.models.budget import Budget, ClientInfo
from app.domain.models.client import Client
from scripts.backfill_budget_clients import backfill_budget_clients


async def _create_budget(
    *,
    uuid: str,
    nombres: str,
    documento: str,
    created_at: datetime,
) -> Budget:
    budget = Budget(
        code=f"BM-20260919-{uuid[-4:]}",
        uuid=uuid,
        client_info=ClientInfo(nombres=nombres, documento=documento),
        items=[],
        created_at=created_at,
    )
    await budget.insert()
    return budget


@pytest.mark.asyncio
async def test_backfill_is_dry_run_safe_and_idempotent():
    now = datetime.now(timezone.utc)
    first = await _create_budget(
        uuid="00000000-0000-4000-8000-000000000001",
        nombres="Cliente inicial",
        documento=" ab 123 ",
        created_at=now - timedelta(days=2),
    )
    latest = await _create_budget(
        uuid="00000000-0000-4000-8000-000000000002",
        nombres="Cliente actualizado",
        documento="AB123",
        created_at=now - timedelta(days=1),
    )
    anonymous = await _create_budget(
        uuid="00000000-0000-4000-8000-000000000003",
        nombres="Sin documento",
        documento="",
        created_at=now,
    )
    original_snapshots = {
        budget.uuid: budget.client_info.model_dump()
        for budget in (first, latest, anonymous)
    }

    preview = await backfill_budget_clients(dry_run=True, batch_size=1)
    assert preview == {
        "processed": 3,
        "associated": 2,
        "without_document": 1,
        "clients_created": 1,
    }
    assert await Client.find_all().count() == 0
    assert all(
        budget.client_id is None
        for budget in await Budget.find_all().to_list()
    )

    first_run = await backfill_budget_clients(batch_size=1)
    assert first_run == preview
    assert await Client.find_all().count() == 1

    client = await Client.find_one(Client.documento == "AB123")
    assert client is not None
    assert client.nombres == "Cliente actualizado"
    original_updated_at = client.updated_at

    persisted = {budget.uuid: budget for budget in await Budget.find_all().to_list()}
    assert persisted[first.uuid].client_id == client.id
    assert persisted[latest.uuid].client_id == client.id
    assert persisted[anonymous.uuid].client_id is None
    assert {
        uuid: budget.client_info.model_dump()
        for uuid, budget in persisted.items()
    } == original_snapshots

    second_run = await backfill_budget_clients(batch_size=1)
    assert second_run["processed"] == 3
    assert second_run["associated"] == 0
    assert second_run["clients_created"] == 0
    assert second_run["without_document"] == 1
    assert await Client.find_all().count() == 1
    unchanged_client = await Client.find_one(Client.documento == "AB123")
    assert unchanged_client is not None
    assert unchanged_client.updated_at == original_updated_at
