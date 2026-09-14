from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from slugify import slugify

from app.database import close_db, init_db
from app.domain.models.category import Category
from app.domain.models.product import Product

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategorySeed:
    name: str
    description: str


CATEGORY_SEEDS: list[CategorySeed] = [
    CategorySeed("Herramientas Neumaticas", "Equipos y accesorios para aire comprimido."),
    CategorySeed("Lijado Industrial", "Discos, rollos y consumibles para lijado profesional."),
    CategorySeed("Pulido y Acabado", "Esponjas, lanas y soluciones para abrillantado."),
    CategorySeed("Preparacion de Superficies", "Insumos para limpieza y acondicionamiento previo."),
    CategorySeed("Enmascarado Tecnico", "Cintas y materiales para proteccion de zonas."),
    CategorySeed("Filtrado de Pintura", "Filtros, coladores y componentes de filtracion."),
    CategorySeed("Aplicacion de Pintura", "Pistolas y elementos para aplicacion controlada."),
    CategorySeed("Consumibles de Taller", "Accesorios de alta rotacion para procesos diarios."),
    CategorySeed("Empaque y Almacenamiento", "Envases y opciones para guardar o transportar."),
    CategorySeed("Accesorios de Conexion", "Acoples, reguladores y piezas de union."),
]

BRANDS: list[str] = [
    "AeroMax",
    "NovaGrip",
    "TitanFlow",
    "BlueForge",
    "ProNexus",
    "VortexLine",
    "IronPulse",
    "PrimeCoat",
    "UltraLink",
    "DeltaFinish",
]

COLORS: list[tuple[str, str]] = [
    ("Rojo Cereza", "#D7263D"),
    ("Azul Electrico", "#1F6FEB"),
    ("Verde Lima", "#7BC950"),
    ("Negro Grafito", "#2F343A"),
    ("Gris Titanio", "#8A9099"),
    ("Amarillo Sol", "#F6C343"),
    ("Naranja Intenso", "#F97316"),
    ("Blanco Polar", "#F8FAFC"),
    ("Morado Vibrante", "#7E57C2"),
    ("Turquesa Brillante", "#14B8A6"),
]

TAG_POOL: list[str] = [
    "automotriz",
    "repintado",
    "acabado_fino",
    "alto_desempeno",
    "uso_profesional",
    "taller",
    "cabina_pintura",
    "detailing",
    "resistente",
    "precision",
    "industrial",
    "durable",
    "rapida_aplicacion",
    "multi_superficie",
    "linea_premium",
]


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Asigna aleatoriamente marca, categorias, colores y tags "
            "a todos los productos registrados en MongoDB."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260914,
        help="Semilla para resultados reproducibles. Default: 20260914",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra resumen de asignaciones sin persistir cambios.",
    )
    return parser.parse_args()


async def _ensure_seed_categories() -> tuple[list[Category], int]:
    categories: list[Category] = []
    created_count = 0
    for category_seed in CATEGORY_SEEDS:
        slug = slugify(category_seed.name)
        existing = await Category.find_one(Category.slug == slug)
        if existing:
            categories.append(existing)
            continue
        created = Category(
            name=category_seed.name,
            slug=slug,
            description=category_seed.description,
            is_active=True,
        )
        await created.insert()
        categories.append(created)
        created_count += 1
    return categories, created_count


def _random_colors(rng: random.Random) -> list[dict[str, str]]:
    selected = rng.sample(COLORS, k=rng.randint(1, 3))
    return [{"name": color_name, "hex": color_hex} for color_name, color_hex in selected]


def _random_tags(rng: random.Random) -> list[str]:
    return rng.sample(TAG_POOL, k=rng.randint(3, 6))


async def run(seed: int, dry_run: bool) -> None:
    rng = random.Random(seed)
    await init_db()
    try:
        categories, created_categories = await _ensure_seed_categories()
        products = await Product.find_all().to_list()
        if not products:
            logger.info("No hay productos registrados para actualizar.")
            return

        updated_count = 0
        preview_rows: list[str] = []
        for product in products:
            selected_categories = rng.sample(categories, k=rng.randint(1, min(3, len(categories))))
            payload = {
                "brand": rng.choice(BRANDS),
                "category_ids": [category.id for category in selected_categories],
                "colors": _random_colors(rng),
                "tags": _random_tags(rng),
            }

            if dry_run:
                preview_rows.append(
                    f"- {product.sku}: {payload['brand']} | "
                    f"cats={len(payload['category_ids'])} | "
                    f"colors={len(payload['colors'])} | tags={len(payload['tags'])}"
                )
                continue

            await product.set(payload)
            updated_count += 1

        logger.info("Categorias base disponibles: %s (creadas: %s)", len(categories), created_categories)
        if dry_run:
            logger.info("DRY RUN: productos analizados=%s", len(products))
            for row in preview_rows[:20]:
                logger.info(row)
            if len(preview_rows) > 20:
                logger.info("... y %s productos adicionales en la simulacion.", len(preview_rows) - 20)
            return

        logger.info("Productos actualizados: %s", updated_count)
    finally:
        await close_db()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    arguments = _build_args()
    asyncio.run(run(seed=arguments.seed, dry_run=arguments.dry_run))
