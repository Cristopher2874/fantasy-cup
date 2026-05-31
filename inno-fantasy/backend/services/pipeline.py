""" Run actual flow """

from backend.services.codex_runner.skill_runner import SkillRuner

def run_skill_pipeline(data):
    runner = SkillRuner().call_skill_runner(data)
    return {"job_result":"success"}