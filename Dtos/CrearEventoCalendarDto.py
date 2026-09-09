from pydantic import BaseModel, Field

class CrearEventoCalendarDto(BaseModel):
    titulo: str = Field(..., title="Título del evento", max_length=200)
    inicio_iso: str = Field(..., title="Inicio ISO 8601, p. ej. 2026-09-10T15:00:00")
    fin_iso: str = Field(..., title="Fin ISO 8601, p. ej. 2026-09-10T16:00:00")
    descripcion: str = Field(default="", title="Descripción")
    zona_horaria: str = Field(default="America/Mexico_City", title="Zona horaria IANA")
