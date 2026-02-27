from pydantic import BaseModel , Field


class CrearProductoDto(BaseModel):
    precio: float = Field(ge=1 , title="Precio" , description="Precio del producto")