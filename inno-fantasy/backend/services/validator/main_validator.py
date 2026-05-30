from typing import Any

from backend.services.validator.zip_handler import ZipHandler
from backend.services.validator.skill_validator import SkillValidator
from schemas.models.structured_outpus import GuardrailDecision

def run_validator(file) -> dict[str,Any]:
    zip_handler = ZipHandler()
    skill_validator = SkillValidator()

    zip_handler.handle_uploaded_zip(file)
    skill_validator.validate_skill(file)

    validator_decision = GuardrailDecision(valid=True, issues=[])

    validator_response = {"status":validator_decision, "job_id": "1234"}

    return validator_response