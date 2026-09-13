from pydantic import BaseModel, Field


class CrearPaginaDto(BaseModel):
    titulo: str = Field(default="Página")
    html_content: str = Field(default="")
