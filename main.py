from fastapi import FastAPI
from sqlalchemy import create_engine , select , update , delete , insert
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///./ProyectDb.db')

Base = automap_base()

Base.prepare(engine , reflect=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
app = FastAPI()


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
        return {"IsSuccess": True, "message" : "no se a encontrado al empleado" , "data": empleado}
    except Exception as e:
        return {"IsSuccess": False, "message" : str(e)}
@app.post("/PostEmpleados")
async def post_empleados():
    db = SessionLocal()
    try:
        
    except Exception as e:
        return {"IsSuccess": False, "message": str(e)}
