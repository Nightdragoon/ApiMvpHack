from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, insert, update, delete
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, Session

engine = create_engine(
    "sqlite:///./ProyectDb.db",
    connect_args={"check_same_thread": False},
)

Base = automap_base()
Base.prepare(autoload_with=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Producto = Base.classes.Producto
Inventario = Base.classes.Inventario

app = FastAPI(title="CRUD Producto & Inventario")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ProductoCreate(BaseModel):
    precio: float = Field(ge=0)


class ProductoUpdate(BaseModel):
    precio: float = Field(ge=0)


class InventarioCreate(BaseModel):
    cantidad: int = Field(ge=0)


class InventarioSet(BaseModel):
    cantidad: int = Field(ge=0)


class InventarioDelta(BaseModel):
    delta: int


def row_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@app.get("/")
def root():
    return {"message": "API OK. Ve a /docs para probar el CRUD."}


# -----------------------------
# CRUD PRODUCTO
# -----------------------------
@app.post("/productos")
def create_producto(payload: ProductoCreate, db: Session = Depends(get_db)):
    stmt = insert(Producto).values(precio=payload.precio)
    result = db.execute(stmt)
    db.commit()
    new_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
    return {"IsSuccess": True, "message": "Producto creado", "id": new_id}


@app.get("/productos")
def list_productos(db: Session = Depends(get_db)):
    rows = db.execute(select(Producto)).scalars().all()
    return {"IsSuccess": True, "data": [row_to_dict(r) for r in rows]}


@app.get("/productos/{id}")
def get_producto(id: int, db: Session = Depends(get_db)):
    producto = db.execute(select(Producto).where(Producto.id == id)).scalar_one_or_none()
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"IsSuccess": True, "data": row_to_dict(producto)}


@app.put("/productos/{id}")
def update_producto(id: int, payload: ProductoUpdate, db: Session = Depends(get_db)):
    exists = db.execute(select(Producto).where(Producto.id == id)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    db.execute(update(Producto).where(Producto.id == id).values(precio=payload.precio))
    db.commit()
    return {"IsSuccess": True, "message": "Producto actualizado"}


@app.delete("/productos/{id}")
def delete_producto(id: int, db: Session = Depends(get_db)):
    db.execute(delete(Inventario).where(Inventario.id_producto == id))
    result = db.execute(delete(Producto).where(Producto.id == id))
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"IsSuccess": True, "message": "Producto eliminado"}


# -----------------------------
# CRUD INVENTARIO
# -----------------------------
@app.post("/productos/{id}/inventario")
def create_inventario(id: int, payload: InventarioCreate, db: Session = Depends(get_db)):
    producto = db.execute(select(Producto).where(Producto.id == id)).scalar_one_or_none()
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    inv = db.execute(select(Inventario).where(Inventario.id_producto == id)).scalar_one_or_none()
    if inv is not None:
        raise HTTPException(status_code=409, detail="Ya existe inventario para este producto")

    db.execute(insert(Inventario).values(id_producto=id, cantidad=payload.cantidad))
    db.commit()
    return {"IsSuccess": True, "message": "Inventario creado"}


@app.get("/productos/{id}/inventario")
def get_inventario(id: int, db: Session = Depends(get_db)):
    inv = db.execute(select(Inventario).where(Inventario.id_producto == id)).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")
    return {"IsSuccess": True, "data": row_to_dict(inv)}


@app.put("/productos/{id}/inventario")
def set_inventario(id: int, payload: InventarioSet, db: Session = Depends(get_db)):
    inv = db.execute(select(Inventario).where(Inventario.id_producto == id)).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")

    db.execute(update(Inventario).where(Inventario.id_producto == id).values(cantidad=payload.cantidad))
    db.commit()
    return {"IsSuccess": True, "message": "Inventario actualizado"}


@app.patch("/productos/{id}/inventario")
def adjust_inventario(id: int, payload: InventarioDelta, db: Session = Depends(get_db)):
    inv = db.execute(select(Inventario).where(Inventario.id_producto == id)).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")

    nueva = int(inv.cantidad) + int(payload.delta)
    if nueva < 0:
        raise HTTPException(status_code=400, detail="No puedes dejar inventario en negativo")

    db.execute(update(Inventario).where(Inventario.id_producto == id).values(cantidad=nueva))
    db.commit()
    return {"IsSuccess": True, "message": "Inventario ajustado", "cantidad": nueva}
