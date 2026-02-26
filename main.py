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

Base.prepare(engine , reflect=True)

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

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

@app.get("/GetEmpleados")
async def get_empleados(id:int):
    db = SessionLocal()
    try:
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
