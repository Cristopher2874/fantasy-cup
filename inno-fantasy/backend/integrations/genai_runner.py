from integrations.oci_client_provider import OCIOpenAIClientProvider
from models.structured_outpus import GuardrailDecision

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
        self._openai_client = OCIOpenAIClientProvider().oci_openai_client
        self._initialized=True

    def call_openai_client(self, prompt)->object|GuardrailDecision:
        try:
            raw_response = self._openai_client.responses.parse(
                model=self._MODEL_ID,
                input=prompt,
                instructions=self._SYSTEM_PROMT,
                text_format=GuardrailDecision,
            )
        except Exception as e:
            return GuardrailDecision(valid=False, issues=[f"error on guardrail: {e}"])

        return raw_response.output_parsed
