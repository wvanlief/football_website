from pydantic import BaseModel

class PlayerOut(BaseModel):
    name: str
    position: str
    form: float

    class Config:
        orm_mode = True
        from_attributes = True
