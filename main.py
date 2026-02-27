from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import sessionmaker, Session
from fastapi import FastAPI , Request
from fastapi.exceptions import RequestValidationError
from fastapi.params import Query
from sqlalchemy import create_engine , select , update , delete , insert , func
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from starlette.responses import JSONResponse
from datetime import date
from Dtos.CrearProductoDto import CrearProductoDto
from Dtos.LoginDto import LoginDto
from Dtos.UpdateCrearProductoDto import UpdateProductoDto
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
    precio: float = Field(ge=1)


class ProductoUpdate(BaseModel):
    precio: float = Field(ge=1)


class InventarioCreate(BaseModel):
    cantidad: int = Field(ge=1)


class InventarioSet(BaseModel):
    cantidad: int = Field(ge=1)


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

@app.get("/GetAllProductos", tags=["productos"])
async def GetAllProductos(solo_activos: bool = False):
    db = SessionLocal()
    try:
        stmt = select(Producto)
        if solo_activos:
            stmt = stmt.where(Producto.activo  == 1)
        result = db.execute(stmt).scalars().all()
        if(len(result) == 0):
            return {"IsSuccess" : False , "message" : "No tienes productos"}

        return { "IsSuccess" : True, "message" : "Productos obtenidos" , "data": result }

    except Exception as e:
        return {"IsSuccess" : False, "message" : str(e)}

    finally:
        db.close()
@app.get("/GetProducto" , tags=["productos"])
async def get_producto(id: Optional[int] = Query(default=None)):
    db = SessionLocal()
    try:
        stmt = select(Producto)
        if id is not None:
            stmt = stmt.where(Producto.id == id)

        result = db.execute(stmt)

        if id is not None:
            producto = result.scalar_one_or_none()
            result.close()
            if producto is None:
                return {"IsSuccess": False, "message": "no se a encontrado el producto"}
            return {"IsSuccess": True, "message": "se a encontrado el producto", "data": producto}

        productos = result.scalars().all()
        result.close()
        if not productos:
            return {"IsSuccess": False, "message": "no se a encontrado ningun producto"}
        return {"IsSuccess": True, "message": "se a encontrado productos", "data": productos}

    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.post("/PostProducto" , tags=["productos"])
async def post_producto(producto: CrearProductoDto):
    db = SessionLocal()
    try:
        stmt = insert(Producto).values(precio = producto.precio , nombre = producto.nombre , activo = producto.activo).returning(Producto)
        result = db.execute(stmt)
        producto_creado = result.scalar_one_or_none()

        if producto_creado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se pudo crear el producto"}

        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a creado el producto", "data": producto_creado}

    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.put("/UpdateProducto" , tags=["productos"])
async def update_producto(producto: UpdateProductoDto):
    db = SessionLocal()
    try:
        stmt = (
            update(Producto)
            .where(Producto.id == producto.id)
            .values(precio = producto.precio , nombre = producto.nombre , activo = producto.activo)
            .returning(Producto)
        )
        result = db.execute(stmt)
        producto_actualizado = result.scalar_one_or_none()

        if producto_actualizado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro el producto"}

        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a actualizado el producto", "data": producto_actualizado}

    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.delete("/DeleteProducto" , tags=["productos"])
async def delete_producto(id: int):
    db = SessionLocal()
    try:
        stmt = delete(Producto).where(Producto.id == id).returning(Producto)
        result = db.execute(stmt)
        producto_eliminado = result.scalar_one_or_none()

        if producto_eliminado is None:
            result.close()
            return {"IsSuccess": False, "message": "no se encontro el producto"}

        result.close()
        db.commit()
        return {"IsSuccess": True, "message": "se a eliminado el producto", "data": producto_eliminado}

    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()
# -----------------------------
# CRUD INVENTARIO
# -----------------------------
@app.post("/productos/{id_producto}/inventario", tags=["inventario"])
def create_inventario(id_producto: int, payload: InventarioCreate, db: Session = Depends(get_db)):
    try:
        producto = db.execute(select(Producto).where(Producto.id == id_producto)).scalar_one_or_none()
        if producto is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        inv = db.execute(select(Inventario).where(Inventario.id_producto == id_producto)).scalar_one_or_none()
        if inv is not None:
            raise HTTPException(status_code=409, detail="Ya existe inventario para este producto")

        db.execute(insert(Inventario).values(id_producto=id_producto, cantidad=payload.cantidad))
        db.commit()
        return {"IsSuccess": True, "message": "Inventario creado"}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.get("/productos/{id_producto}/inventario", tags=["inventario"])
def get_inventario(id_producto: int, db: Session = Depends(get_db)):
    try:
        inv = db.execute(select(Inventario).where(Inventario.id_producto == id_producto)).scalar_one_or_none()
        if inv is None:
            raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")
        return {"IsSuccess": True, "data": row_to_dict(inv)}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.put("/productos/{id_producto}/inventario", tags=["inventario"])
def set_inventario(id_producto: int, payload: InventarioSet, db: Session = Depends(get_db)):
    try:
        inv = db.execute(select(Inventario).where(Inventario.id_producto == id_producto)).scalar_one_or_none()
        if inv is None:
            raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")

        db.execute(update(Inventario).where(Inventario.id_producto == id_producto).values(cantidad=payload.cantidad))
        db.commit()
        return {"IsSuccess": True, "message": "Inventario actualizado"}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()


@app.patch("/productos/{id_producto}/inventario", tags=["inventario"])
def adjust_inventario(id_producto: int, payload: InventarioDelta, db: Session = Depends(get_db)):
   try:
       inv = db.execute(select(Inventario).where(Inventario.id_producto == id_producto)).scalar_one_or_none()
       if inv is None:
           raise HTTPException(status_code=404, detail="Inventario no encontrado para este producto")

       nueva = int(inv.cantidad) + int(payload.delta)
       if nueva < 0:
           raise HTTPException(status_code=400, detail="No puedes dejar inventario en negativo")

       db.execute(update(Inventario).where(Inventario.id_producto == id_producto).values(cantidad=nueva))
       db.commit()
       return {"IsSuccess": True, "message": "Inventario ajustado", "cantidad": nueva}
   except Exception as e:
       return {"IsSuccess": False, "message": str(e)}
   finally:
       db.close()

@app.get("/getAllInventario", tags=["inventario"])
def get_all_inventario():
    db = SessionLocal()
    try:
        stmt = select(Inventario)
        result = db.execute(stmt).scalars().all()
        if len(result) == 0:
            return {"IsSuccess": False, "message": "No hay nada en inventario"}
        return {"IsSuccess": True, "message" : "inventario obtenido",  "data": result}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

#crud empleados
@app.post("/PostEmpleados", tags=["empleados"])
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
@app.put("/UpdateEmpleado", tags=["empleados"])
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


@app.delete("/DeleteEmpleado", tags=["empleados"])
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

@app.get("/GetAllEmpleados", tags=["empleados"])
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
@app.get("/GetCaja", tags=["Caja"])
async def get_caja(fecha_inicial: Optional[date] = Query(default=None), fecha_final: Optional[date] = Query(default=None)):
    db = SessionLocal()
    try:
        stmt = select(Base.classes.Caja)
        if fecha_inicial is not None:
            stmt = stmt.where(Base.classes.Caja.dia >= fecha_inicial)
        if fecha_final is not None:
            stmt = stmt.where(Base.classes.Caja.dia <= fecha_final)
        result = db.execute(stmt)
        caja = result.scalars().all()
        if not caja:
            return {"IsSuccess": False, "message": "no se a encontrado la venta"}
        result.close()
        return {"IsSuccess": True, "message" : "se a encontrado la venta" , "data": caja}
    except Exception as e:
        return {"IsSuccess": False, "message" : str(e)}
    finally:
        db.close()

@app.post("/PostCaja", tags=["Caja"])
async def post_caja(caja: CrearCajaDto):
    db = SessionLocal()
    try:
        check = select(Producto).where(Producto.id == caja.idf_producto)
        result_check = db.execute(check)
        checking = result_check.scalar_one_or_none()
        if checking is None:
            return {"IsSuccess": False, "message": "no hay registro del producto"}
        no_inventario = select(Inventario.cantidad).where(Inventario.id_producto == caja.idf_producto).where(Inventario.cantidad > 0)
        result_no_inventario = db.execute(no_inventario)
        if result_no_inventario is None:
            return {"IsSuccess": False , "message": "no hay registro del producto en el inventario"}
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

@app.put("/UpdateCaja", tags=["Caja"])
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


@app.delete("/DeleteCaja", tags=["Caja"])
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

@app.get("/GetAllCaja", tags=["Caja"])
async def get_all_caja():
    db = SessionLocal()
    try:
        stmt = select(Caja).order_by(Caja.id)
        result = db.execute(stmt).scalars().all()
        if len(result) == 0:
            return {"IsSuccess": False, "message": "no se encontro la caja"}
        return {"IsSuccess": True,"message": "todas las ventas" ,  "data": result}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

@app.post("/login" , tags=["login"])
async def login(login: LoginDto):
    db = SessionLocal()
    try:
        stmt = select(Empleado).where(Empleado.login == login.username).where(Empleado.contrasena == login.password)
        result = db.execute(stmt)
        log = result.scalar_one_or_none()
        if log is None:
            return {"IsSuccess": False, "message": "no esta registrado comuniquese con un administrador "}
        return {"IsSuccess": True, "message": "login suceeded", "data": log}
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()

@app.get("/Obtencion_ganancias_baundrate" , tags=["Burnrate"])
async def obtenerPerdida():
    db = SessionLocal()
    try:
        mes = date.today().replace(day=1)
        stmt = (
            select(
                Producto.id.label("producto_id"),
                Producto.precio.label("precio"),  # cambia si tu columna se llama distinto
                func.count(Caja.id).label("vendidos"),  # cuántas veces aparece en Caja
                Inventario.cantidad.label("stock")  # cambia si se llama stock/existencia/cantidad
            )
            .select_from(Caja)
            .join(Producto, Producto.id == Caja.idf_producto)
            .outerjoin(Inventario, Inventario.id_producto == Producto.id)
            .where(Caja.dia >= mes)
            .group_by(Producto.id, Producto.precio, Inventario.cantidad)
            .order_by(func.count(Caja.id).desc())
        )
        result = db.execute(stmt)
        productos = result.all()
        if len(productos) == 0:
            return {"IsSuccess": False, "message": "no se encontrado la producto"}
        lista_ganancias_mes = [r.vendidos * r.stock for r in productos]
        lista_perdidas_mes = [r.precio * r.stock for r in productos]
        ganancias_totales = sum(lista_ganancias_mes)
        perdidas_totales = sum(lista_perdidas_mes)
        data = [
            {
                "producto_id": r.producto_id,
                "precio": r.precio,
                "vendidos": r.vendidos,
                "stock": r.stock,
                "ganancia_mes": r.vendidos * r.precio,
                "perdida_mes": r.precio * r.stock

            }
            for r in productos
        ]

        runway = ganancias_totales / perdidas_totales
        return {"IsSuccess": True, "message": "se a encontrado la producto" , "data": data , "ganancias_mes_totales" : ganancias_totales ,"perdida_mes_totales" : perdidas_totales , "runway" : runway}

        #de un producto sacarle su venta del mes y su inventario y multiplicarlo por su precio



    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
    finally:
        db.close()