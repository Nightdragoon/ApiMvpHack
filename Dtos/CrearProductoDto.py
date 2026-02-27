from pydantic import BaseModel , Field


class CrearProductoDto(BaseModel):
    precio: float = Field(ge=1 , title="Precio" , description="Precio del producto")
    nombre: str = Field(... , title="Nombre" , min_length=1 , max_length=100)
    activo: int = Field(... , title="Activo" , ge=0 , le=1)
