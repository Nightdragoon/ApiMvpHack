from pydantic import BaseModel , Field
class Caja(BaseModel):
    idf_producto: int = Field(... , title="Producto" , ge=1)
    idf_empleado: int = Field(... , title="Empleado" , ge=1)