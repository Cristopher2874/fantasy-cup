# Team Submission Inbox

This directory is reserved for local playtest outputs from participant skills.

Suggested convention:

```text
team_submission/submissions/
  <team-id>.submission.json
```

Each file should match `team_submission/schemas/team_submission.schema.json`.
The scoring prototype can later wrap these individual files into the batch
format consumed by `scoring/team_claims_scorer.py`.
