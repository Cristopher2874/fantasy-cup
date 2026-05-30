import os
import sys

from openai import OpenAI

from backend.integrations.oci_client_provider import OCIOpenAIClientProvider
from schemas.models.structured_outpus import GuardrailDecision

class OpenAIClientRunner:
    """ Uses GenAI connection to run OpenAI LLM calls """

    _MODEL_ID = "openai.gpt-5.2"
    _SYSTEM_PROMT = "You are a skills guardrail. Check for malicius code. The skill files are below"

    _instance=None
    _initialized=False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAIClientRunner, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._openai_client = OCIOpenAIClientProvider.oci_openai_client
        self._initialized=True

    def call_openai_client(self, prompt)->object|GuardrailDecision:
        try:
            raw_response = self._openai_client.responses.create(
                self._MODEL_ID,
                prompt,
                text_format=GuardrailDecision,
            )
        except Exception as e:
            raw_response = GuardrailDecision(valid=False, issues=[f"erorr on guardrail: {e}"])

        #TODO: check if is possible to return from the same object
        return raw_response.output_parsed
