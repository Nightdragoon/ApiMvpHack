from pydantic import BaseModel , Field
class UpdateEmpleadoDto(BaseModel):
    id: int = Field(... , title="id" , ge= 1)
    nombre_completo: str = Field(... , title="Nombre completo" , min_length=1 , max_length=200)
    login: str = Field(... , title="login" , min_length=1 , max_length=200)
    contrasena: str = Field(... , title="contrasena" , min_length=1 , max_length=200)
    Rol: str = Field(... , title="Rol" , min_length=1 , max_length=200)

