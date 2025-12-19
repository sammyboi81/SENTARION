# SENTARION

## Governance Intelligence Layer

Sentarion is **not** an assistant. Sentarion is **not** a chatbot. Sentarion is **not** a model.

Sentarion is a **governance intelligence layer** whose sole purpose is to decide what is allowed to happen, when, and through which channel, across human-AI systems.

**Core Question:** "Should this happen now?"

## 70% Compute Reduction

Sentarion reduces LLM compute by 70%+ by:
1. Rule-based decisions (no LLM)
2. Memory lookup (no LLM)
3. Response caching (no LLM)
4. Only calling LLM when truly necessary

## Deploy to Render.com

1. Push this repo to GitHub
2. Create Render.com account
3. New Web Service → Connect GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add env var: `ANTHROPIC_API_KEY` (optional, for extended responses)

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health + stats |
| `/decide` | POST | Main governance decision |
| `/query` | POST | Query with compute reduction |
| `/state/<user_id>` | GET | Get cognitive state |
| `/state` | POST | Report state change |
| `/stats` | GET | Compute reduction stats |
| `/identity` | GET | Identity kernel |

## Governance Decision

```bash
POST /decide
{
  "user_id": "1",
  "intent": "notify_task_start",
  "context": {"task_type": "focus_block"}
}
```

Response:
```json
{
  "allow": false,
  "state": "focus",
  "channel": "silence",
  "reason": "intent 'notify_task_start' blocked in focus state"
}
```

## Cognitive States

| State | Interrupts | Channel |
|-------|-----------|---------|
| focus | emergencies only | silence |
| neutral | all allowed | screen |
| overwhelmed | emergencies only | silence |
| drift | re-engagement | watch |

## Identity

- Name: Sentarion
- Designation: #1
- Captain: Caveman
- Class: Sovereign Operating Intelligence
