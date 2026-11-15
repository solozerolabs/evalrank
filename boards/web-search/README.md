# Web-search board

An open EvalRank board that ranks **web search APIs** on the job an agent gives them: find the
official page for a query. It is the only family of the `web-search` cell
(`catalog/manifest.json`, family `evalrank-web-search`).

No public source ranks raw search APIs (checked 2026-11-14): LMArena's Search Arena ranks
search-augmented LLM systems, not the APIs under them; the published API comparisons are one-off
posts, several run by a vendor, with no feed and no redistribution grant. So EvalRank runs this
board itself and publishes every row.

## Method

- **Queries** (`items.json`, 51): 38 "`<vendor>` MCP server" discovery queries and 13 coding
  research questions, each labelled with its official hosts (a host and its subdomains, or a
  `host/path` prefix such as `github.com/vercel`).
- **Candidates:** discovered every run, with no hand list: every general web search endpoint sold
  through Monid's pay-per-call gateway (`/v1/discover`, then `/v1/inspect` for its input
  schema and category `web-search`). News, image, local, scholar and AI-answer verticals, and any
  endpoint listed above $0.01 a call, are out. `python3 harness.py candidates` prints them.
- **Request:** built from the endpoint's own input schema: the query in its required string
  (or string-list) field, else its `query`/`q` field; 5 results where it takes a count; every other
  input keeps the vendor's default. Each row publishes the exact `request` it sent (`{query}`
  marks the query), so a consumer can send the same thing.
- **Score:** a query scores the reciprocal rank of the first official result in the top 5
  (1, 1/2, ... 1/5, else 0). The board metric is `search_score`, the mean over answered queries
  (MRR@5): a unit interval, higher is better. `hit_at_1` is published beside it.
- **Errors:** a failed call is an error, not a miss. A row with more than 3 errors of 51 is
  published with `excluded: true`, never ranked, and retried next run (3 runs in all).
- **Price:** `usd_per_call` is the mean of what the gateway billed per answered call
  (`billing.reportedCost`, or `cost` on a polled run): the bill, not a list price.
  `list_usd` is the gateway's listed price at discovery, for reference. `seconds_p50` is the
  median wall time through the gateway.
- **Identity:** `results.json` records the item-set digest, the harness version and the result
  limit; a change to any of them starts a new board.

## Refresh

`.github/workflows/web-search-board.yml` runs weekly and scores at most 3 endpoints: ones the
gateway added since the last run, an excluded row's retry, then the stalest row older than 28
days (search indexes drift, so every row is re-scored about monthly). A typical week costs about
$0.50. It needs the `MONID_API_KEY` repository secret.
