# axiomn-sdk

Thin Python client for the AXIOMN intent routing API. No FastAPI, no
langdetect, no embedding model — just an HTTP client, so any app can depend
on it without pulling in the server's dependencies.

```python
from axiomn_sdk import AXIOMNClient

client = AXIOMNClient(base_url="http://localhost:8000")
result = client.intent("Explain how black holes form")

print(result.route)   # "local_ai"
print(result.result)  # "[local] learn answer for: ..."
```

When a request escalates to a human (`action.type == "await_human"`),
the answer arrives later — block on it, or poll yourself:

```python
result = client.intent("Trouve un expert en droit fiscal pour moi")
if result.action.type == "await_human":
    ticket = client.wait_for_human(result.action.payload["ticket_id"], timeout=300)
    print(ticket.answer)  # what the human eventually replied

# operator side: resolve a pending ticket
client.answer_ticket(ticket_id, "Contactez Maître Dupont.")
```

## Install (editable, for local development against this monorepo)

```bash
pip install -e sdk/
```
