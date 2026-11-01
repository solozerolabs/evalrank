# EvalRank MCP

Public MCP adapter for portable fixtures and the launch HTTP operations.

Package metadata:

- Distribution: `evalrank-mcp`
- Import: `evalrank_mcp`
- Runtime dependencies: `evalrank-core==0.0.0`, `evalrank-sdk==0.0.0`
- License: `Apache-2.0`

`list_tools()` exposes `evalrank.fixture`, `evalrank.decide`, `evalrank.decision_receipt`, `evalrank.use_cases`, and `evalrank.benchmark_health`.

```python
from evalrank_mcp import call_tool

call_tool("evalrank.fixture", {"kind": "fingerprint"})
call_tool("evalrank.fixture", {"kind": "raw-entry"})
call_tool("evalrank.fixture", {"kind": "problem"})
call_tool("evalrank.fixture", {"kind": "observation"})
call_tool("evalrank.fixture", {"kind": "use-cases"})

call_tool("evalrank.use_cases", base_url="https://evalrank.example")
call_tool("evalrank.benchmark_health", base_url="https://evalrank.example")
call_tool("evalrank.decide", {"query": {...}, "share": True}, base_url="https://evalrank.example")
call_tool("evalrank.decision_receipt", {"receipt_id": "receipt_..."}, base_url="https://evalrank.example")
```

The MCP host configures `base_url` outside model-controlled tool arguments. The decision tool advertises a closed `DecisionQueryV2`-shaped input and validates it again through the SDK. `share` defaults to false. Problem Details responses are returned as MCP errors without rewriting their typed public fields.

There are no legacy recommendation or scoring-stage tools. This package does not start a server, discover services, read environment defaults, add auth, retry, or call private services.
