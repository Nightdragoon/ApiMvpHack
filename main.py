from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, insert, update, delete
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import FastAPI , Request
from fastapi.exceptions import RequestValidationError
from fastapi.params import Query
from sqlalchemy import create_engine , select , update , delete , insert
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from starlette.responses import JSONResponse
from datetime import date

from Dtos import UpdateCajaDto
from Dtos.EmpleadoDto import EmpleadoDto
from Dtos.UpdateEmpleadoDto import UpdateEmpleadoDto
from Dtos.CrearCajaDto import CrearCajaDto
from Dtos.UpdateCajaDto import UpdateCajaDto
from typing import Optional
engine = create_engine('sqlite:///./ProyectDb.db')

Base = automap_base()
Base.prepare(autoload_with=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Empleado = Base.classes.Empleados
Caja = Base.classes.Caja
app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "IsSuccess": False,
            "message": "Validación falló",
            "data": exc.errors(),   # aquí vienen los fields faltantes y por qué
        },
    )

Producto = Base.classes.Producto
Inventario = Base.classes.Inventario

app = FastAPI(title="CRUD Producto & Inventario")


def get_db():
    db = SessionLocal()
    try:
        yield db
        stmt = select(Base.classes.Empleados).where(Base.classes.Empleados.id == id)
        result = db.execute(stmt)
        empleado = result.scalar_one_or_none()
        if empleado is None:
            return {"IsSuccess": False, "message": "se a encontrado al empleado"}
        result.close()
        return {"IsSuccess": True, "message" : "no se a encontrado al empleado" , "data": empleado}
    except Exception as e:
        return {"IsSuccess": False, "message" : str(e)}
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
@app.post("/PostEmpleados")
async def post_empleados(empleado: EmpleadoDto):
    db = SessionLocal()
    try:
        stmt = insert(Empleado).values(nombre_completo= empleado.nombre_completo ,  login = empleado.login , contrasena = empleado.contrasena , Rol = empleado.Rol).returning(Empleado)
        result = db.execute(stmt)
        empleado_creado = result.scalar_one_or_none()
        if empleado_creado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se pudo crear al empleado"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message" : "se a creado al empleado" , "data": empleado_creado}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()
#crud empleado
@app.put("/UpdateEmpleado")
async def update_empleado(empleado: UpdateEmpleadoDto):
    db = SessionLocal()
    try:
        stmt = update(Empleado).where(Empleado.id == empleado.id).values(nombre_completo= empleado.nombre_completo , login = empleado.login , contrasena = empleado.contrasena , Rol = empleado.Rol).returning(Empleado)
        result = db.execute(stmt)
        empleado_actualizado = result.scalar_one_or_none()
        if empleado_actualizado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro al empleado"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a actualizado al empleado", "data": empleado_actualizado}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.delete("/DeleteEmpleado")
async def delete_empleado(id: int):
    db = SessionLocal()
    try:
        stmt = delete(Empleado).where(Empleado.id == id).returning(Empleado)
        result = db.execute(stmt)
        empleado_eliminado = result.scalar_one_or_none()
        if empleado_eliminado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro al empleado"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a eliminado al empleado", "data": empleado_eliminado}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

@app.get("/GetAllEmpleados")
async def get_all_empleados():
    db = SessionLocal()
    try:
        stmt = select(Empleado)
        result = db.execute(stmt)
        empleados = result.scalars().all()
        if not empleados:
            return {"IsSuccess": False, "message": "no se encontraron empleados"}
        return {"IsSuccess": True, "message": "se encontraron los empleados", "data": empleados}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

#crud caja
@app.get("/GetCaja")
async def get_caja(fecha_inicial: Optional[date] = Query(default=None), fecha_final: Optional[date] = Query(default=None)):
    db = SessionLocal()
    try:
        stmt = select(Base.classes.Caja)
        if fecha_inicial is not None:
            stmt = stmt.where(Base.classes.Caja.dia >= fecha_inicial)
        if fecha_final is not None:
            stmt = stmt.where(Base.classes.Caja.dia <= fecha_final)
        result = db.execute(stmt)
        caja = result.scalar_one_or_none()
        if caja is None:
            return {"IsSuccess": False, "message": "no se a encontrado la venta"}
        result.close()
        return {"IsSuccess": True, "message" : "se a encontrado la venta" , "data": caja}
    except Exception as e:
        return {"IsSuccess": False, "message" : str(e)}
    finally:
        db.close()

@app.post("/PostCaja")
async def post_caja(caja: CrearCajaDto):
    db = SessionLocal()
    try:
        stmt = insert(Caja).values(idf_producto = caja.idf_producto , idf_empleado = caja.idf_empleado , dia = caja.dia).returning(Caja)
        result = db.execute(stmt)
        caja_creada = result.scalar_one_or_none()
        if caja_creada is None:
            result.close()
            return {"IsSuccess": False, "message": "no se pudo crear la caja"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message" : "se a creado la caja" , "data": caja_creada}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

@app.put("/UpdateCaja")
async def update_caja(caja: UpdateCajaDto):
    db = SessionLocal()
    try:
        stmt = update(Caja).where(Caja.id == caja.id).values(idf_producto = caja.idf_producto , idf_empleado = caja.idf_empleado , dia = caja.dia).returning(Caja)
        result = db.execute(stmt)
        caja_actualizada = result.scalar_one_or_none()
        if caja_actualizada is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro la caja"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a actualizado la caja", "data": caja_actualizada}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.delete("/DeleteCaja")
async def delete_caja(id: int):
    db = SessionLocal()
    try:
        stmt = delete(Caja).where(Caja.id == id).returning(Caja)
        result = db.execute(stmt)
        caja_eliminada = result.scalar_one_or_none()
        if caja_eliminada is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro la caja"}
        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a eliminado la caja", "data": caja_eliminada}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()
