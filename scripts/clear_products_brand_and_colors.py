import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from settings.config import settings


async def main():
    print(f"Conectando a MongoDB en: {settings.masked_mongo_uri()}")
    print(f"Base de datos: {settings.mongo_db_name}")
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    total = await db.products.count_documents({})
    print(f"Total productos en colección: {total}")

    # Consultar productos que tienen marca no vacía o colores no vacíos
    with_brand = await db.products.count_documents({"brand": {"$exists": True, "$nin": ["", None]}})
    with_colors = await db.products.count_documents({"colors": {"$exists": True, "$not": {"$size": 0}}})
    print(f"Productos con marca configurada: {with_brand}")
    print(f"Productos con colores configurados: {with_colors}")

    # Mostrar algunos ejemplos antes de actualizar
    print("\n--- Muestra previa (3 productos) ---")
    cursor = db.products.find({}, {"name": 1, "sku": 1, "brand": 1, "colors": 1}).limit(3)
    async for doc in cursor:
        print(f"SKU: {doc.get('sku')} | Nombre: {doc.get('name')} | Marca: {doc.get('brand')} | Colores: {doc.get('colors')}")

    # Actualizar todos los productos para eliminar la marca y los colores
    # Se establece brand='' y colors=[] para que coincidan con los valores predeterminados sin configuración
    result = await db.products.update_many(
        {},
        {
            "$set": {
                "brand": "",
                "colors": []
            }
        }
    )
    print(f"\nDocumentos encontrados: {result.matched_count}")
    print(f"Documentos modificados: {result.modified_count}")

    # Verificación post-actualización
    remaining_brand = await db.products.count_documents({"brand": {"$exists": True, "$nin": ["", None]}})
    remaining_colors = await db.products.count_documents({"colors": {"$exists": True, "$not": {"$size": 0}}})
    print(f"\nProductos restantes con marca: {remaining_brand}")
    print(f"Productos restantes con colores: {remaining_colors}")

    print("\n--- Muestra posterior (3 productos) ---")
    cursor_after = db.products.find({}, {"name": 1, "sku": 1, "brand": 1, "colors": 1}).limit(3)
    async for doc in cursor_after:
        print(f"SKU: {doc.get('sku')} | Nombre: {doc.get('name')} | Marca: {repr(doc.get('brand'))} | Colores: {doc.get('colors')}")

    client.close()
    print("\nOperación completada con éxito.")


if __name__ == "__main__":
    asyncio.run(main())
