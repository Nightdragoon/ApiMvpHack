from pydantic import BaseModel , Field
from datetime import date
class UpdateCajaDto(BaseModel):
    id: int = Field(... , title="id" , ge=1)
    idf_producto: int = Field(... , title="Producto" , ge=1)
    idf_empleado: int = Field(... , title="Empleado" , ge=1)
    dia: date = Field(default_factory=date.today, title="Dia")