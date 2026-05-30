from backend.integrations.genai_runner import OpenAIClientRunner
from schemas.models.structured_outpus import GuardrailDecision

class SkillGuardrail:
    """ LLM guardrail to check for malicius code or instructions """

    def __init__(self):
        self._client_runner = OpenAIClientRunner()

    def validate_with_guardrail(self)->GuardrailDecision:
        validation = self._client_runner.call_openai_client("sample")

        return validation
