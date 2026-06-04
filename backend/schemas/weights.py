from pydantic import BaseModel, Field

class WeightUpdate(BaseModel):
    elo: float = Field(..., ge=0.0, le=1.0)
    odds: float = Field(..., ge=0.0, le=1.0)
    form: float = Field(..., ge=0.0, le=1.0)
    narrative: float = Field(..., ge=0.0, le=1.0)
