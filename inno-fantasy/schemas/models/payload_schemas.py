from pydantic import BaseModel

class UploadSkillRequest(BaseModel):
    file:object
    team_id:str