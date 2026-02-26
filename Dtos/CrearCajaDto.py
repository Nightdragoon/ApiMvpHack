from pydantic import BaseModel , Field
from datetime import date
class CrearCajaDto(BaseModel):
    idf_producto: int = Field(... , title="Producto" , ge=1)
    idf_empleado: int = Field(... , title="Empleado" , ge=1)
    dia: date = Field(default_factory=date.today, title="Dia")