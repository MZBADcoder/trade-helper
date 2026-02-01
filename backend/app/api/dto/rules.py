from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    call_put: str = "both"
    dte_bucket: str = "3m"


class RuleOut(RuleCreate):
    id: int

