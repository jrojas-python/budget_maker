from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from pymongo import DESCENDING

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.database import close_db, init_db
from app.domain.models.budget import Budget
from app.infrastructure.repositories.client_repo import ClientRepository


async def backfill_budget_clients(
    *,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict[str, int]:
    """Asocia presupuestos históricos con clientes sin alterar sus snapshots."""
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")

    client_repo = ClientRepository()
    stats = {
        "processed": 0,
        "associated": 0,
        "without_document": 0,
        "clients_created": 0,
    }
    simulated_documents: set[str] = set()
    offset = 0

    while True:
        budgets = await (
            Budget.find_all()
            .sort([("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(offset)
            .limit(batch_size)
            .to_list()
        )
        if not budgets:
            break
        for budget in budgets:
            stats["processed"] += 1
            snapshot = budget.client_info
            documento = "".join(snapshot.documento.split()).upper()
            if not documento:
                stats["without_document"] += 1
                continue

            existing = await client_repo.get_by_documento(documento)
            if dry_run:
                if existing is None and documento not in simulated_documents:
                    stats["clients_created"] += 1
                    simulated_documents.add(documento)
                if budget.client_id is None or existing is None or budget.client_id != existing.id:
                    stats["associated"] += 1
                continue

            client_data: dict[str, Any] = {
                "nombres": snapshot.nombres.strip(),
                "apellidos": snapshot.apellidos.strip(),
                "email": snapshot.email.strip(),
                "documento": documento,
                "compania": snapshot.compania.strip(),
                "direccion": snapshot.direccion.strip(),
                "observaciones": snapshot.observaciones.strip(),
            }
            if existing is None:
                stats["clients_created"] += 1
                client = await client_repo.create(client_data)
            else:
                client = existing
            if budget.client_id != client.id:
                await budget.set({"client_id": client.id})
                stats["associated"] += 1
        offset += len(budgets)

    return stats


async def _run_cli(dry_run: bool, batch_size: int) -> None:
    await init_db()
    try:
        stats = await backfill_budget_clients(dry_run=dry_run, batch_size=batch_size)
    finally:
        await close_db()
    mode = "simulación" if dry_run else "ejecución"
    print(
        f"Backfill ({mode}): {stats['processed']} procesados, "
        f"{stats['associated']} asociados, {stats['clients_created']} clientes creados, "
        f"{stats['without_document']} sin documento."
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asocia presupuestos históricos con clientes por documento.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Informa sin persistir cambios.")
    parser.add_argument("--batch-size", type=int, default=100, help="Tamaño de cada lote.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_run_cli(dry_run=args.dry_run, batch_size=args.batch_size))
