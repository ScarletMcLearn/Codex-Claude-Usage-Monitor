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

Unsupported values remain `NULL` and render as `Unavailable`. Numeric zero
renders as `0`; the UI must not coerce unknown values to zero.

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

Reported, derived, estimated, and unavailable values are labeled distinctly in
the UI. Estimated context or repeated-context tokens are never styled as
provider-reported billing tokens.

## Storage

SQLite tables are prefixed with `forensic_`:

- `forensic_sources`: local file/log source, parser version, checkpoint,
  source identity/fingerprint, reset counts/reasons, and safe diagnostics.
- `forensic_sessions`: agent/session/model/project summary.
- `forensic_turns`: per-event/turn token and provenance fields.
- `forensic_messages`: locally exposed user/assistant/tool text.
- `forensic_context_blocks`: context fingerprints for duplicate detection.
- `forensic_tool_calls`: tool invocation evidence when exposed.
- `forensic_commands`: command/stdout/stderr evidence when exposed.
- `forensic_file_accesses`: explicit tool/file access evidence, path/content
  repetition flags, and estimated context contribution where output is exposed.
- `forensic_relationships`: observed parent-message/sidechain evidence. Parent
  UUID links are not labeled as separate sub-agents unless source evidence proves
  that semantic.
- `forensic_raw_events`: immutable raw JSON event payloads.
- `forensic_exports`: export metadata.

Ingestion is incremental via file byte checkpoints. Append-only JSONL is safe to
refresh repeatedly; unchanged refreshes ingest zero new events. Incomplete final
JSONL lines are not ingested and do not advance the checkpoint; once completed,
they ingest exactly once. If a file is truncated, replaced, rewritten, or parsed
with a new parser version, the checkpoint resets to the beginning and the source
diagnostics record the reset reason. Identity uses Windows-compatible file stat
fields plus a small beginning-content fingerprint; the collector avoids hashing
entire large files during routine refresh.

## Relationship Rollups

Relationship evidence remains conservative. Claude `parentUuid` is a
parent-message relationship by default and is provenance only. It does not prove
a spawned agent/session. Sidechain-like evidence may be treated as execution
ancestry for derived rollups.

Rollup terms:

- `direct_usage`: token usage directly attributed to the selected session.
- `descendant_usage`: usage from reachable descendant sessions over eligible
  ancestry edges.
- `inclusive_usage`: direct plus descendant usage.

Global totals still sum direct session usage only, so descendants are not counted
twice. Rollups retain provenance: descendant IDs, relationship types used,
skipped edges, cycles, and `quality=derived`. Cycles, duplicate edges, self-edges,
orphans, and unsupported relationship types are reported and skipped rather than
recursed indefinitely.

## UI

The dashboard includes a Token Forensics section:

- evidence refresh;
- zero-token counters;
- source diagnostics with deterministic health, parser/checkpoint state, reset
  counts/reasons, truncation/replacement flags, and passive collection mode;
- source/entity counts;
- expensive turns;
- repeated context;
- session list with click-through drill-down;
- chronological session turn timeline;
- turn evidence view for input/output, token labels, context, tools, commands,
  raw event, and parser provenance;
- tool, command, context, and file hotspots;
- file-access drill-down for path, operation, range, size, repetition, context
  contribution, and quality;
- relationship evidence for parent-message/sidechain links;
- derived direct/descendant/inclusive usage when relationship semantics justify it;
- summary export;
- full forensic export with warning.

Large content is not rendered in full by default. API queries are bounded and the
UI shows previews.

Source diagnostics are operational health views. They show sanitized source
identity, source type, parser version, file size, checkpoint offset, event
counts, malformed/duplicate counts, reset/truncation/replacement flags, and
last event time. They do not show raw prompts, assistant responses, source-code
contents, command output, tool output, or credentials.

Deterministic source health:

- `Healthy`: source is accessible, has processed events, and has no current
  parser error, malformed/reset, truncation, replacement, or rotation evidence.
- `Idle`: source is valid and unchanged; no new local telemetry was ingested.
- `Warning`: malformed events, duplicate-heavy parser skips, checkpoint reset,
  truncation, replacement, or rotation evidence exists.
- `Error`: source has a current collector/parser error.

## Exports

Summary exports include manifest, overview, agents, sessions, and turns.

Full exports add messages, tools, commands, context blocks, file accesses,
relationships, and raw events. Full exports can contain prompts, model output,
source code excerpts, and command output, so the UI/API require explicit warning
acknowledgment. Exports are local ZIP files and are never uploaded automatically.
Session, agent, provider, model, project, and date filters can scope exports;
related rows are filtered by session IDs. The manifest includes deterministic
record counts for each included JSONL file and scope metadata. Scoped
relationships whose other endpoint is outside the export are marked
`external_not_included` rather than left unexplained.

## Support Matrix

Allowed status values are `Supported`, `Partially supported`,
`Unavailable from source telemetry`, and `Not implemented`.

| Capability | Codex | Claude | Source/Evidence | UI | Export |
| --- | --- | --- | --- | --- | --- |
| session ID | Supported | Supported | JSONL session fields/path-derived IDs | Supported | Supported |
| turn ID | Supported | Supported | Deterministic event/message IDs | Supported | Supported |
| model | Partially supported | Supported | Codex when event exposes model; Claude `message.model` | Supported | Supported |
| provider | Partially supported | Partially supported | Source metadata when exposed; otherwise agent-derived | Supported | Supported |
| project/repository | Partially supported | Partially supported | `cwd`/project path when source exposes it | Supported | Supported |
| branch/worktree | Unavailable from source telemetry | Partially supported | Claude `gitBranch`; Codex observed source lacks branch | Supported | Supported |
| raw user input | Supported | Supported | Message text when local JSONL exposes content | Supported | Supported |
| raw assistant output | Supported | Supported | Message text when local JSONL exposes content | Supported | Supported |
| reported input tokens | Partially supported | Supported | Usage fields when present | Supported | Supported |
| reported output tokens | Partially supported | Supported | Usage fields when present | Supported | Supported |
| total tokens | Partially supported | Supported | Reported or deterministic sum of reported fields | Supported | Supported |
| cached tokens | Partially supported | Partially supported | Usage cache fields when present | Supported | Supported |
| reasoning tokens | Partially supported | Partially supported | Usage/reasoning fields when present | Supported | Supported |
| context usage | Partially supported | Partially supported | Deterministic estimates from exposed context/file blocks | Supported | Supported |
| cumulative usage | Partially supported | Partially supported | Cumulative-to-delta framework where source exposes cumulative fields | Supported | Supported |
| token provenance | Supported | Supported | Per-row quality/provenance JSON | Supported | Supported |
| tools | Supported | Supported | Codex tool events; Claude `tool_use` blocks | Supported | Supported |
| tool output | Supported | Supported | Tool output when local telemetry exposes it | Supported | Supported |
| commands | Partially supported | Partially supported | Command-shaped tool payloads/output | Supported | Supported |
| command output | Partially supported | Partially supported | stdout/stderr when exposed | Supported | Supported |
| file access | Partially supported | Partially supported | Explicit file/tool access evidence only | Supported | Supported |
| file repetition | Supported | Supported | Deterministic path/content hashes | Supported | Supported |
| repeated context | Supported | Supported | Deterministic content hashes | Supported | Supported |
| relationships | Partially supported | Partially supported | Parent/child evidence when telemetry exposes links | Supported | Supported |
| sidechains | Partially supported | Partially supported | Eligible sidechain relationship evidence only | Supported | Supported |
| true child sessions | Unavailable from source telemetry | Partially supported | Only when source evidence proves child-session semantics | Supported | Supported |
| direct usage | Supported | Supported | Session-local usage rows | Supported | Supported |
| descendant usage | Partially supported | Partially supported | Derived over eligible cycle-safe relationship edges | Supported | Supported |
| inclusive usage | Partially supported | Partially supported | Direct plus descendant usage when relationships qualify | Supported | Supported |
| retries | Not implemented | Not implemented | No deterministic retry model yet | Not implemented | Not implemented |
| fallbacks | Not implemented | Not implemented | No deterministic fallback model yet | Not implemented | Not implemented |
| compaction | Partially supported | Partially supported | Raw compaction events retained; semantic accounting partial | Supported | Supported |
| raw event retention | Supported | Supported | Raw JSONL event copy | Supported | Supported |
| source diagnostics | Supported | Supported | `forensic_sources` checkpoint/parser/reset fields | Supported | Supported |
| hotspots | Supported | Supported | Tool/command/context/file aggregate queries | Supported | Supported |
| summary export | Supported | Supported | Safe ZIP summary manifest/data | Supported | Supported |
| full forensic export | Supported | Supported | Warning-gated ZIP with raw retained evidence | Supported | Supported |

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

Monitoring flow:

```text
AI agent performs normal work
        |
agent writes its normal local telemetry
        |
forensic collector passively reads telemetry
        |
source-specific deterministic parser
        |
SQLite
        |
analytics / monitoring UI / export
```

The forensic monitor does not create model requests in order to collect
telemetry.

Agent usage consumes tokens normally. The monitor observes already-generated
local telemetry, consumes local CPU/RAM/disk only, and adds 0 model-generation
requests.

## Limitations

Telemetry formats vary and may change. Best-effort parsers preserve raw events so
future versions can reparse richer fields. Hidden reasoning and non-exposed
client context cannot be recovered. Unknown values are not guessed. File access
and relationship rows are recorded only when source telemetry explicitly exposes
the evidence.
