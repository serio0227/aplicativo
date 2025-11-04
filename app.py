import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from enum import Enum
import math

# --- 1. Modelos de Datos (Como en types.ts) ---

class ProductCategory(str, Enum):
    SUELA = "Suela"
    CUERO = "Cuero"
    HILO = "Hilo"
    PLANTILLA = "Plantilla"
    ACCESORIO = "Accesorio"

class MovementType(str, Enum):
    INBOUND = "Entrada"
    OUTBOUND = "Salida"

class UserRole(str, Enum):
    ADMIN = "Admin"
    USER = "Usuario"

class Product(BaseModel):
    id: str
    code: str
    name: str
    category: ProductCategory
    quantity: int
    minStock: int
    unitCost: float
    location: str
    supplierId: str

class Supplier(BaseModel):
    id: str
    name: str
    contact: str

class Movement(BaseModel):
    id: str
    productId: str
    userId: str
    type: MovementType
    quantity: int
    date: datetime = Field(default_factory=datetime.now)
    origin: Optional[str] = None
    destination: Optional[str] = None
    reason: Optional[str] = None

class User(BaseModel):
    id: str
    name: str
    password: str # En una app real, esto debería ser un hash
    role: UserRole

class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

# Modelo para la creación de movimientos, para no requerir id, date, y userId en el body
class MovementCreate(BaseModel):
    productId: str
    type: MovementType
    quantity: int
    origin: Optional[str] = None
    destination: Optional[str] = None
    reason: Optional[str] = None

# --- 2. Base de Datos Simulada ---

db: Dict[str, List] = {
    "products": [
        Product(id="p1", code="SL-001", name="Suela de Goma Runner", category=ProductCategory.SUELA, quantity=150, minStock=50, unitCost=12.5, location="A1-R2", supplierId="s1"),
        Product(id="p2", code="CR-001", name="Cuero Nobuk Marrón", category=ProductCategory.CUERO, quantity=80, minStock=30, unitCost=45.0, location="B2-R1", supplierId="s2"),
        Product(id="p3", code="HL-001", name="Hilo de Nylon Negro", category=ProductCategory.HILO, quantity=500, minStock=100, unitCost=5.0, location="C1-R5", supplierId="s1"),
        Product(id="p4", code="PL-002", name="Plantilla de Espuma", category=ProductCategory.PLANTILLA, quantity=200, minStock=40, unitCost=7.2, location="A1-R3", supplierId="s3"),
        Product(id="p5", code="AC-010", name="Ojetillos Metálicos", category=ProductCategory.ACCESORIO, quantity=10, minStock=20, unitCost=0.1, location="C1-R1", supplierId="s2"),
    ],
    "suppliers": [
        Supplier(id="s1", name="Insumos del Sur S.A.", contact="juan.perez@insusur.com"),
        Supplier(id="s2", name="Cueros del Norte", contact="maria.gomez@cuerosnorte.com"),
        Supplier(id="s3", name="Comodidad Total", contact="info@comodidad.com"),
    ],
    "movements": [
        Movement(id="m1", productId="p2", userId="u1", type=MovementType.OUTBOUND, quantity=10, date=datetime.now() - timedelta(days=5), destination="Producción Lote 102"),
        Movement(id="m2", productId="p3", userId="u2", type=MovementType.INBOUND, quantity=200, date=datetime.now() - timedelta(days=15), origin="Proveedor Insumos del Sur"),
        Movement(id="m3", productId="p5", userId="u1", type=MovementType.INBOUND, quantity=500, date=datetime.now() - timedelta(days=120), origin="Proveedor Cueros del Norte"),
    ],
    "users": [
        User(id="u1", name="Valentina", password="123", role=UserRole.USER),
        User(id="u2", name="Admin", password="admin", role=UserRole.ADMIN),
    ]
}

STORAGE_RATE = 0.20 # 20% Tasa de costo de almacenamiento anual

# --- 3. Inicialización de la App FastAPI ---

app = FastAPI(
    title="Inventario VADAF - API",
    description="API para gestionar el inventario de una fábrica de zapatos.",
    version="1.0.0"
)

# --- 4. Endpoints de la API ---

@app.get("/products", response_model=List[Product], tags=["Products"])
def get_products():
    """Obtiene la lista de todos los productos."""
    return db["products"]

@app.get("/suppliers", response_model=List[Supplier], tags=["Suppliers"])
def get_suppliers():
    """Obtiene la lista de todos los proveedores."""
    return db["suppliers"]

@app.get("/movements", response_model=List[Movement], tags=["Movements"])
def get_movements():
    """Obtiene el registro de todos los movimientos."""
    return db["movements"]

@app.post("/movements", response_model=Movement, tags=["Movements"])
def add_movement(movement_data: MovementCreate, user_id: str = "u1"): # Simula un usuario logueado
    """Registra un nuevo movimiento de inventario."""
    product = next((p for p in db["products"] if p.id == movement_data.productId), None)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if movement_data.type == MovementType.OUTBOUND and movement_data.quantity > product.quantity:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {product.quantity}")

    # Actualizar stock del producto
    if movement_data.type == MovementType.INBOUND:
        product.quantity += movement_data.quantity
    else: # OUTBOUND
        product.quantity -= movement_data.quantity

    new_movement = Movement(
        id=f"m{len(db['movements']) + 1}",
        userId=user_id,
        **movement_data.dict()
    )
    db["movements"].append(new_movement)
    return new_movement

@app.put("/users/{user_id}", response_model=User, tags=["Users"])
def update_user(user_id: str, user_data: UserUpdate):
    """Actualiza el nombre o la contraseña de un usuario."""
    user = next((u for u in db["users"] if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.password is not None:
        # En una aplicación real, aquí se manejaría el hash de la nueva contraseña
        user.password = user_data.password
        
    return user

# --- Endpoint para el Panel de Indicadores (Reports) ---

@app.get("/reports/kpis", tags=["Reports"])
def get_kpis():
    """Calcula y devuelve los KPIs principales del inventario."""
    products = db["products"]
    movements = db["movements"]

    # Valor Total del Inventario
    total_inventory_value = sum(p.quantity * p.unitCost for p in products)

    # Costo de Bienes Vendidos (COGS)
    cost_of_goods_sold = 0
    product_map = {p.id: p for p in products}
    for m in movements:
        if m.type == MovementType.OUTBOUND:
            product = product_map.get(m.productId)
            cost_of_goods_sold += m.quantity * (product.unitCost if product else 0)

    # Rotación de Inventario
    inventory_turnover = (cost_of_goods_sold / total_inventory_value) if total_inventory_value > 0 else 0

    # Días de Inventario Disponible (DIO)
    daily_cogs = cost_of_goods_sold / 365
    days_of_inventory = (total_inventory_value / daily_cogs) if daily_cogs > 0 else 0

    # Costo de Almacenamiento
    storage_cost = total_inventory_value * STORAGE_RATE

    # Índice de Obsolescencia
    ninety_days_ago = datetime.now() - timedelta(days=90)
    products_with_recent_movement = {m.productId for m in movements if m.date > ninety_days_ago}
    obsolete_products_count = len([p for p in products if p.id not in products_with_recent_movement])
    obsolescence_rate = (obsolete_products_count / len(products) * 100) if products else 0
    
    # Productos con Stock Bajo
    low_stock_products = [p for p in products if 0 < p.quantity <= p.minStock]

    return {
        "totalInventoryValue": total_inventory_value,
        "inventoryTurnover": inventory_turnover,
        "daysOfInventory": days_of_inventory,
        "storageCost": storage_cost,
        "obsolescenceRate": obsolescence_rate,
        "lowStockProductsCount": len(low_stock_products)
    }

# --- Ejecución de la App (para desarrollo) ---

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
