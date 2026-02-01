from pydantic import BaseModel


class Alert(BaseModel):
    id: int
    ticker: str
    rule_key: str
    priority: str
    message: str
    created_at: str | None = None
