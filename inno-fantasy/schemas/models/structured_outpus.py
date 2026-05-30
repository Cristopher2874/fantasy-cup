from pydantic import BaseModel

class GuardrailDecision(BaseModel):
    valid: bool
    issues: list[str]