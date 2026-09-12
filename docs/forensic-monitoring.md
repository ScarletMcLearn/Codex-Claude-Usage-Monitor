# Zero-Token Forensic Monitoring

Forensic monitoring is additive to the quota dashboard. It reads local evidence
already emitted by agents and stores normalized records plus raw events for later
analysis. It does not call LLM APIs, start agents, or run prompt commands.

## Passive Sources

| Agent | Passive source | Tokens | Input/output | Tools | Commands | Raw events | Quality |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex | `$CODEX_HOME/sessions`, `projects`, `history` JSONL | Reported when JSONL exposes usage fields; otherwise unknown | Captured from `response_item` message content | Parsed from `function_call`, `custom_tool_call`, web/tool/image search events | Parsed when command-shaped tool payloads expose command/stdout/stderr | Yes | reported/estimated/unknown |
| Claude Code | `$CLAUDE_CONFIG_DIR` or `~/.claude` JSONL under `sessions`, `projects`, `history` | Reported from assistant `message.usage` when present; otherwise unknown | Captured from `message.content` text blocks | Parsed from `tool_use` and `tool_result` content blocks | Parsed when command-shaped payloads expose command/stdout/stderr | Yes | reported/estimated/unknown |
| Free-AI | local router logs from configured Free-AI repo | Unknown unless logs expose tokens in future parser | Not captured by current log summary | Not captured | Not captured | Summary only | unknown |
| Antigravity | copied `/usage` snapshot text file | Quota snapshot only; forensic tokens unavailable | Not captured | Not captured | Not captured | Summary only | unknown |

Unsupported values remain `NULL` and render as `Unavailable from source telemetry`.

## Observed Source Formats

Codex rollout JSONL rows observed locally use top-level fields:

```text
timestamp, ordinal, type, payload
```

Supported Codex event shapes:

- `session_meta`: session id, cwd, provider/source metadata where exposed.
- `response_item` with payload `type=message`: user/assistant text blocks.
- `response_item` with payload `function_call`, `function_call_output`,
  `custom_tool_call`, `custom_tool_call_output`, `tool_search_*`,
  `web_search_call`, `image_generation_call`: tool evidence.
- `response_item` with payload `reasoning`: summary/content if exposed.
- `event_msg` with payload `token_count`: token/count evidence only when `info`
  exposes token fields; rate-limit percentages are not treated as model tokens.
- `compacted`, `turn_context`, and unknown event types: retained as raw events.

Claude Code project JSONL rows observed locally use top-level fields such as:

```text
type, uuid, parentUuid, sessionId, timestamp, cwd, gitBranch, message
```

Supported Claude event shapes:

- `user`: `message.role`, string or block `message.content`.
- `assistant`: `message.model`, `message.content`, `message.usage`,
  `requestId`, response id, stop fields where exposed in raw provenance.
- `tool_use`/`tool_result` blocks inside `message.content`.
- `attachment`, `file-history-snapshot`, `file-history-delta`, `cost-state`,
  mode/permission/system events: retained as raw events and parsed only for
  generic text where safely exposed.

## Data Quality

- `reported`: source telemetry directly exposed token values.
- `derived`: deterministic calculation from authoritative values.
- `estimated`: local deterministic estimate from stored text. Current estimate is
  character-count based and never presented as billed provider tokens.
- `unknown`: source did not expose the value.

## Storage

SQLite tables are prefixed with `forensic_`:

- `forensic_sources`: local file/log source, parser version, checkpoint.
- `forensic_sessions`: agent/session/model/project summary.
- `forensic_turns`: per-event/turn token and provenance fields.
- `forensic_messages`: locally exposed user/assistant/tool text.
- `forensic_context_blocks`: context fingerprints for duplicate detection.
- `forensic_tool_calls`: tool invocation evidence when exposed.
- `forensic_commands`: command/stdout/stderr evidence when exposed.
- `forensic_raw_events`: immutable raw JSON event payloads.
- `forensic_exports`: export metadata.

Ingestion is incremental via file byte checkpoints. Append-only JSONL is safe to
refresh repeatedly; unchanged refreshes ingest zero new events.

## UI

The dashboard includes a Token Forensics section:

- evidence refresh;
- zero-token counters;
- source/entity counts;
- expensive turns;
- repeated context;
- session list with click-through drill-down;
- chronological session turn timeline;
- turn evidence view for input/output, token labels, context, tools, commands,
  raw event, and parser provenance;
- tool, command, and context hotspots;
- summary export;
- full forensic export with warning.

Large content is not rendered in full by default. API queries are bounded and the
UI shows previews.

## Exports

Summary exports include manifest, overview, agents, sessions, and turns.

Full exports add messages, tools, commands, context blocks, and raw events. Full
exports can contain prompts, model output, source code excerpts, and command
output, so the UI/API require explicit warning acknowledgment. Exports are local
ZIP files and are never uploaded automatically.

## Zero-Token Guarantee

Forensic monitoring code path uses:

| Operation | Purpose | Can generate AI request? | Automatically invoked? |
| --- | --- | --- | --- |
| Read JSONL files | Parse Codex/Claude local sessions | No | Yes |
| Read Free-AI logs | Count passive router successes | No | Yes |
| Read Antigravity snapshot file | Parse copied usage text | No | Yes |
| SQLite reads/writes | Store/search evidence | No | Yes |
| ZIP creation | Local export | No | User-triggered |

Network endpoint audit:

| Endpoint | Purpose | Generative? | Token-consuming? | Used by forensic monitor? |
| --- | --- | --- | --- | --- |
| None | N/A | No | No | No |

Subprocess audit:

| Command | Purpose | Can generate AI request? | Automatically invoked by forensic monitor? |
| --- | --- | --- | --- |
| None | N/A | No | No |

Existing quota adapters are separate from forensic ingestion. Some quota paths can
run provider commands when enabled by existing settings; those are not used by
`/api/forensics/refresh`.

## Limitations

Telemetry formats vary and may change. Best-effort parsers preserve raw events so
future versions can reparse richer fields. Hidden reasoning and non-exposed
client context cannot be recovered. Unknown values are not guessed. Dedicated
file-access and sub-agent hierarchy tables are not yet present; file/child-agent
evidence is available only when source telemetry exposes it through messages,
tools, commands, or raw provenance.
