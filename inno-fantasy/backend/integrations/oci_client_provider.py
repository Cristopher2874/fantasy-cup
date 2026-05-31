import httpx
import logging

from openai import OpenAI
from oci_genai_auth import OciUserPrincipalAuth
from backend.config.config_provider import GlobalConfigProvider

class OCIOpenAIConfigKeyNotFound(Exception):
    """Raised when required config keys are missing."""

class OCIOpenAIClientProvider:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCIOpenAIClientProvider, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._scfg=GlobalConfigProvider()
        self._openai_endpoint = self._scfg.get_config_value("oci_openai","default_endpoint","")
        self._oci_api_key = self._scfg.get_config_value("oci", "api_key", "not-used")
        self._oci_project = self._scfg.get_config_value("oci", "project", "")
        self._oci_compartment_id = self._scfg.get_config_value("oci", "compartment", "")
        self._oci_profile = self._scfg.get_config_value("oci", "profile", "DEFAULT")
        self._oci_config_file = self._scfg.get_config_value("oci", "configFile", "~/.oci/config")
        
        #verify that the env is set correctly
        self._verify_required_config()

        # build the clients for responses and agent mode
        self.oci_openai_client = self._build_openai_client()

        #init the singleton
        self._initialized = True

    def _verify_required_config(self) -> None:
        missing: list[str] = []
        if not self._openai_endpoint:
            missing.append("openai.service_endpoint")
        if not self._oci_compartment_id:
            missing.append("oci.compartment")
        if not self._oci_project:
            missing.append("oci.project")

        if missing:
            raise OCIOpenAIConfigKeyNotFound(
                f"Missing required config keys for OCIOpenAIClientProvider in '{self.config_path}': {', '.join(missing)}"
            )

    # Helper for adding project headers to OpenAI-compatible API calls.
    def _default_headers(self) -> dict[str, str]:
        return {
            "OpenAI-Project": self._oci_project,
            "opc-compartment-id": self._oci_compartment_id,
            "compartment-id": self._oci_compartment_id
        }

    # Client for responses.create use cases
    def _build_openai_client(self) -> OpenAI:
        client = OpenAI(
            base_url=self._openai_endpoint,
            api_key=self._oci_api_key,
            project=self._oci_project,
            default_headers=self._default_headers(),
            http_client=httpx.Client(auth=self._get_user_auth()),
        )

        return client
    
    def _get_user_auth(self) -> OciUserPrincipalAuth:
        auth=OciUserPrincipalAuth(
            config_file=self._oci_config_file,
            profile_name=self._oci_profile,
        )

        return auth

    # Logger for debug, call as:
    # OpenAIClientProvider().get_logger 
    def get_logger(self):
        self.logger = logging.getLogger("openai")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())

        return self.logger
