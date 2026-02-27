from pydantic import BaseModel, Field

class UpdateProductoDto(BaseModel):
    id: int = Field(ge=1 , title="Id del producto" , description="Id del producto")
    precio: float = Field(ge=1 , title="Precio" , description="Precio del producto")