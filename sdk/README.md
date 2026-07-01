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

## Install (editable, for local development against this monorepo)

```bash
pip install -e sdk/
```
