from pydantic import BaseModel , Field


class CrearProductoDto(BaseModel):
    precio: float = Field(ge=0)