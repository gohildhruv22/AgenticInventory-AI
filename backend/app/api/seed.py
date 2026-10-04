from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.inventory_item import InventoryItem
from app.models.user import User

router = APIRouter(tags=["seed"])

SEED_ITEMS = [
    {"name": "Wireless Mouse", "sku": "ELEC-001", "category": "Electronics", "current_stock": 5, "reorder_threshold": 10, "safety_stock": 3, "lead_time_days": 5, "unit_cost": Decimal("25.99"), "supplier_email": "orders@techsupply.com"},
    {"name": "USB-C Hub", "sku": "ELEC-002", "category": "Electronics", "current_stock": 120, "reorder_threshold": 15, "safety_stock": 5, "lead_time_days": 7, "unit_cost": Decimal("45.50"), "supplier_email": "orders@techsupply.com"},
    {"name": "Mechanical Keyboard", "sku": "ELEC-003", "category": "Electronics", "current_stock": 8, "reorder_threshold": 12, "safety_stock": 4, "lead_time_days": 6, "unit_cost": Decimal("89.99"), "supplier_email": "orders@techsupply.com"},
    {"name": "27\" Monitor", "sku": "ELEC-004", "category": "Electronics", "current_stock": 30, "reorder_threshold": 5, "safety_stock": 2, "lead_time_days": 10, "unit_cost": Decimal("349.00"), "supplier_email": "orders@techsupply.com"},
    {"name": "Webcam HD", "sku": "ELEC-005", "category": "Electronics", "current_stock": 0, "reorder_threshold": 8, "safety_stock": 3, "lead_time_days": 4, "unit_cost": Decimal("59.99"), "supplier_email": "orders@techsupply.com"},
    {"name": "A4 Copy Paper (Box)", "sku": "OFFC-001", "category": "Office Supplies", "current_stock": 200, "reorder_threshold": 50, "safety_stock": 20, "lead_time_days": 3, "unit_cost": Decimal("32.00"), "supplier_email": "sales@officeworld.com"},
    {"name": "Ballpoint Pens (50pk)", "sku": "OFFC-002", "category": "Office Supplies", "current_stock": 15, "reorder_threshold": 20, "safety_stock": 10, "lead_time_days": 3, "unit_cost": Decimal("12.50"), "supplier_email": "sales@officeworld.com"},
    {"name": "Sticky Notes (12pk)", "sku": "OFFC-003", "category": "Office Supplies", "current_stock": 80, "reorder_threshold": 25, "safety_stock": 10, "lead_time_days": 3, "unit_cost": Decimal("8.99"), "supplier_email": "sales@officeworld.com"},
    {"name": "Binder Clips (Box)", "sku": "OFFC-004", "category": "Office Supplies", "current_stock": 45, "reorder_threshold": 15, "safety_stock": 5, "lead_time_days": 3, "unit_cost": Decimal("6.50"), "supplier_email": "sales@officeworld.com"},
    {"name": "Whiteboard Markers (Set)", "sku": "OFFC-005", "category": "Office Supplies", "current_stock": 3, "reorder_threshold": 10, "safety_stock": 5, "lead_time_days": 4, "unit_cost": Decimal("15.00"), "supplier_email": "sales@officeworld.com"},
    {"name": "Steel Sheet (1mm)", "sku": "RAW-001", "category": "Raw Materials", "current_stock": 500, "reorder_threshold": 100, "safety_stock": 50, "lead_time_days": 14, "unit_cost": Decimal("85.00"), "supplier_email": "procurement@metalworks.com"},
    {"name": "Aluminum Rod (6ft)", "sku": "RAW-002", "category": "Raw Materials", "current_stock": 75, "reorder_threshold": 30, "safety_stock": 10, "lead_time_days": 12, "unit_cost": Decimal("42.00"), "supplier_email": "procurement@metalworks.com"},
    {"name": "Copper Wire (100m)", "sku": "RAW-003", "category": "Raw Materials", "current_stock": 20, "reorder_threshold": 25, "safety_stock": 10, "lead_time_days": 10, "unit_cost": Decimal("120.00"), "supplier_email": "procurement@metalworks.com"},
    {"name": "Plastic Pellets (25kg)", "sku": "RAW-004", "category": "Raw Materials", "current_stock": 150, "reorder_threshold": 40, "safety_stock": 15, "lead_time_days": 7, "unit_cost": Decimal("55.00"), "supplier_email": "procurement@metalworks.com"},
    {"name": "Rubber Gaskets (100pk)", "sku": "RAW-005", "category": "Raw Materials", "current_stock": 300, "reorder_threshold": 80, "safety_stock": 30, "lead_time_days": 8, "unit_cost": Decimal("28.50"), "supplier_email": "procurement@metalworks.com"},
    {"name": "Coffee Beans (5kg)", "sku": "FOOD-001", "category": "Food & Beverage", "current_stock": 2, "reorder_threshold": 5, "safety_stock": 2, "lead_time_days": 5, "unit_cost": Decimal("62.00"), "supplier_email": "orders@freshgoods.com"},
    {"name": "Green Tea (200 bags)", "sku": "FOOD-002", "category": "Food & Beverage", "current_stock": 40, "reorder_threshold": 10, "safety_stock": 5, "lead_time_days": 4, "unit_cost": Decimal("18.50"), "supplier_email": "orders@freshgoods.com"},
    {"name": "Bottled Water (24pk)", "sku": "FOOD-003", "category": "Food & Beverage", "current_stock": 60, "reorder_threshold": 20, "safety_stock": 10, "lead_time_days": 2, "unit_cost": Decimal("9.99"), "supplier_email": "orders@freshgoods.com"},
    {"name": "Protein Bars (Box)", "sku": "FOOD-004", "category": "Food & Beverage", "current_stock": 25, "reorder_threshold": 15, "safety_stock": 5, "lead_time_days": 5, "unit_cost": Decimal("24.00"), "supplier_email": "orders@freshgoods.com"},
    {"name": "Oat Milk (12 cartons)", "sku": "FOOD-005", "category": "Food & Beverage", "current_stock": 10, "reorder_threshold": 8, "safety_stock": 3, "lead_time_days": 3, "unit_cost": Decimal("35.00"), "supplier_email": "orders@freshgoods.com"},
    {"name": "All-Purpose Cleaner (5L)", "sku": "CLEAN-001", "category": "Cleaning Supplies", "current_stock": 30, "reorder_threshold": 10, "safety_stock": 5, "lead_time_days": 4, "unit_cost": Decimal("14.50"), "supplier_email": "bulk@cleanpro.com"},
    {"name": "Disinfectant Wipes (6pk)", "sku": "CLEAN-002", "category": "Cleaning Supplies", "current_stock": 50, "reorder_threshold": 20, "safety_stock": 10, "lead_time_days": 3, "unit_cost": Decimal("22.00"), "supplier_email": "bulk@cleanpro.com"},
    {"name": "Trash Bags (100pk)", "sku": "CLEAN-003", "category": "Cleaning Supplies", "current_stock": 7, "reorder_threshold": 15, "safety_stock": 5, "lead_time_days": 3, "unit_cost": Decimal("18.00"), "supplier_email": "bulk@cleanpro.com"},
    {"name": "Hand Soap Refill (5L)", "sku": "CLEAN-004", "category": "Cleaning Supplies", "current_stock": 20, "reorder_threshold": 8, "safety_stock": 3, "lead_time_days": 4, "unit_cost": Decimal("16.50"), "supplier_email": "bulk@cleanpro.com"},
    {"name": "Microfiber Cloths (20pk)", "sku": "CLEAN-005", "category": "Cleaning Supplies", "current_stock": 40, "reorder_threshold": 12, "safety_stock": 5, "lead_time_days": 3, "unit_cost": Decimal("11.99"), "supplier_email": "bulk@cleanpro.com"},
]


@router.post("/inventory/seed", status_code=201)
async def seed_inventory(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # Check if already seeded
    result = await db.execute(select(InventoryItem).limit(1))
    if result.scalar_one_or_none():
        return {"message": "Database already seeded", "count": 0}

    count = 0
    for item_data in SEED_ITEMS:
        item = InventoryItem(**item_data)
        db.add(item)
        count += 1

    await db.flush()
    return {"message": f"Seeded {count} items successfully", "count": count}
