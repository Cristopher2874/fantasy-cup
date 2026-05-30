""" Validates the skills uploaded from zip """
from backend.services.validator.skill_guardrail import SkillGuardrail
from schemas.models.structured_outpus import GuardrailDecision
#uses the temp zip files or route
# requires names and routes normalization since linux is case sensitive but windows isn't

class SkillValidator:

    def __init__(self):
        self._guardrail = SkillGuardrail()
        self._zip_file=None #temp??

    def _normalize_file_names(self)->None:
        pass
    
    def _valid_folder_structure(self)->bool:
        #validates that the folder strucutre is according to sKILLS standards
        return True
    
    def _no_scripts_on_files(self)->bool:
        #validates that the skills contains no executables
        return True
    
    def validate_skill(self, file)->bool:
        if not (self._normalize_file_names() and self._valid_folder_structure() and self._no_scripts_on_files()):
            guardrail_decision = GuardrailDecision(valid=True, issues=["sintaxis validation failed"])
        
        guardrail_decision = self._guardrail.validate_with_guardrail(f"files: {self._zip_file}")
        

        return guardrail_decision