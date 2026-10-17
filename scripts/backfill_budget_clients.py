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
from app.domain.models.client import Client
from app.infrastructure.repositories.client_repo import ClientRepository


async def ensure_client_indexes() -> None:
    """Asegura que el índice de email exista y remueve el índice obsoleto de documento si está presente."""
    collection = Client.get_motor_collection()
    existing_indexes = await collection.index_information()
    if "uq_client_documento_non_empty" in existing_indexes:
        await collection.drop_index("uq_client_documento_non_empty")
    if "uq_client_email_non_empty" not in existing_indexes:
        await collection.create_index(
            [("email", 1)],
            name="uq_client_email_non_empty",
            unique=True,
            partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
        )


async def backfill_budget_clients(
    *,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict[str, int]:
    """Asocia presupuestos históricos con clientes por email sin alterar sus snapshots."""
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")

    if not dry_run:
        await ensure_client_indexes()

    client_repo = ClientRepository()
    stats = {
        "processed": 0,
        "associated": 0,
        "without_email": 0,
        "clients_created": 0,
    }
    simulated_emails: set[str] = set()
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
            email = snapshot.email.strip().lower() if snapshot.email else ""
            if not email:
                stats["without_email"] += 1
                continue

            existing = await client_repo.get_by_email(email)
            if dry_run:
                if existing is None and email not in simulated_emails:
                    stats["clients_created"] += 1
                    simulated_emails.add(email)
                if budget.client_id is None or existing is None or budget.client_id != existing.id:
                    stats["associated"] += 1
                continue

            client_data: dict[str, Any] = {
                "nombres": snapshot.nombres.strip(),
                "apellidos": snapshot.apellidos.strip(),
                "email": email,
                "documento": snapshot.documento.strip(),
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
        f"{stats['without_email']} sin email."
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asocia presupuestos históricos con clientes por correo electrónico.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Informa sin persistir cambios.")
    parser.add_argument("--batch-size", type=int, default=100, help="Tamaño de cada lote.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_run_cli(dry_run=args.dry_run, batch_size=args.batch_size))

