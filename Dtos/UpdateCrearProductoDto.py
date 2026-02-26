from pydantic import BaseModel, Field

class UpdateProductoDto(BaseModel):
    id: int
    precio: float = Field(ge=0)