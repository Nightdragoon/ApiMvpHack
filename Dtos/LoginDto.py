from pydantic import BaseModel , Field
class LoginDto(BaseModel):
    username: str = Field(... , title="Username" , min_length=1 , max_length=200)
    password: str = Field(... , min_length=1 , max_length=200)
