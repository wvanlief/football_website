from pydantic import BaseModel, ConfigDict

class PlayerOut(BaseModel):
    name: str
    position: str
    form: float

    model_config = ConfigDict(from_attributes=True)
