
import asyncio
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.inventory_item import InventoryItem

async def main():
    async with AsyncSessionLocal() as s:
        total = (await s.execute(select(func.count(InventoryItem.id)))).scalar_one()
        rows = (await s.execute(select(InventoryItem.category, func.count(InventoryItem.id)).group_by(InventoryItem.category))).all()
        print(f"TOTAL={total}")
        for cat, n in rows:
            print(f"  {cat}: {n}")

if __name__ == "__main__":
    asyncio.run(main())

