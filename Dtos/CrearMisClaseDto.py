from pydantic import BaseModel, Field

class MisClaseDto(BaseModel):
    materia: str = Field(..., title="Materia", max_length=100)
    aula: str = Field(default="", title="Aula", max_length=100)
    horario: str = Field(default="", title="Horario de inicio", max_length=100)
    dia: str = Field(default="Lunes", title="Día", max_length=100)
