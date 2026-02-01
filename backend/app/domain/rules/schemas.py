from pydantic import BaseModel, Field


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    call_put: str = "both"
    dte_bucket: str = "3m"


class Rule(RuleIn):
    id: int
