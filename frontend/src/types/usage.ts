// Mirrors backend/src/claude_codex_monitor/models/*.py - keep in sync.

export type Provider = 'claude' | 'codex' | 'antigravity' | 'free_ai'

export type DataQuality = 'verified' | 'derived' | 'estimated' | 'stale' | 'unavailable'

export type UsageLevel = 'normal' | 'moderate' | 'high' | 'critical' | 'exhausted' | 'unknown'

export interface UsageLimit {
  provider: Provider
  profile_id: string
  window_id: string
  window_label: string
  window_duration_minutes: number | null
  used_percent: number | null
  used_units: number | null
  max_units: number | null
  remaining_percent: number | null
  resets_at_utc: string | null
  reset_confirmed: boolean
  quality: DataQuality
  unavailable_reason: string | null
  observed_at_utc: string
  source_detail: Record<string, unknown>
}

export interface ProfileStatus {
  provider: Provider
  profile_id: string
  profile_key: string
  label: string
  friendly_name: string | null
  sanitized_source: string
  discovery_source: string
  is_active: boolean
  is_authenticated: boolean | null
  last_refresh_utc: string | null
  last_success_utc: string | null
  last_error: string | null
  is_stale: boolean
  executable_found: boolean
}

export interface Settings {
  auto_refresh_enabled: boolean
  refresh_interval_seconds: number
  history_retention_days: number
  theme: 'light' | 'dark' | 'system'
  display_timezone: string
  hide_sensitive_paths: boolean
  notifications_enabled: boolean
  notify_at_80_percent: boolean
  notify_at_95_percent: boolean
  notify_on_exhaustion: boolean
  notify_on_auth_required: boolean
  notify_on_repeated_failures: boolean
  notify_on_reset: boolean
  profile_overrides: Array<{
    provider: Provider
    profile_id: string
    enabled: boolean
    friendly_name: string | null
  }>
}

export interface Summary {
  total_profiles: number
  queried_successfully: number
  need_auth: number
  over_80_percent: number
  over_95_percent: number
  next_reset_utc: string | null
  stale_or_failed: number
  generated_at_utc: string
}

export interface HistoryRow {
  id: number
  profile_key: string
  window_id: string
  window_label: string | null
  used_percent: number | null
  remaining_percent: number | null
  resets_at_utc: string | null
  reset_confirmed: number
  quality: DataQuality
  unavailable_reason: string | null
  observed_at_utc: string
  source_detail_json: string | null
  is_reset_boundary: number
  provider: Provider
  profile_label: string | null
  friendly_name: string | null
}

export type HistoryRange = 'today' | '7d' | '30d' | '90d' | 'all'

export interface ProfileDiagnostics {
  provider: Provider
  profile_id: string
  profile_key: string
  discovery_source: string
  sanitized_config_path: string
  last_command_result: string | null
  parser_used: string | null
  last_successful_query_utc: string | null
  current_error: string | null
  suggested_action: string | null
  executable_path_sanitized: string | null
  notifier_db_available: boolean | null
  notifier_db_reason: string | null
}

export interface UsageReportRow {
  profile_key: string
  provider: Provider
  label: string
  ok: boolean
  source: string
  message: string
  limits: UsageLimit[]
}

export interface UsageReport {
  generated_at_utc: string
  profiles_checked: number
  rows: UsageReportRow[]
}

export interface ForensicOverview {
  counts: Record<string, number>
  agents: Array<{ agent: string; sessions: number; total_tokens: number | null }>
  expensive_turns: Array<{
    turn_id: string
    session_id: string
    event_type: string | null
    timestamp_utc: string | null
    model: string | null
    input_tokens: number | null
    output_tokens: number | null
    total_tokens: number | null
    token_quality: string
    user_preview: string | null
    assistant_preview: string | null
  }>
  repeated_context: Array<{
    content_hash: string
    occurrences: number
    chars: number
    estimated_tokens: number | null
    first_seen_utc: string | null
    latest_seen_utc: string | null
    category: string
    source: string
    preview: string | null
  }>
  zero_token_counters: {
    monitor_model_generation_requests: number
    monitor_completion_requests: number
    monitor_agent_prompt_invocations: number
  }
}

export interface ForensicSession {
  session_id: string
  agent: string
  provider: string | null
  model: string | null
  project_path: string | null
  started_at_utc: string | null
  ended_at_utc: string | null
  raw_event_count: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  token_quality: string
}

export interface ForensicTurn {
  turn_id: string
  session_id: string
  turn_index: number
  event_type: string | null
  timestamp_utc: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  cached_tokens: number | null
  cache_write_tokens: number | null
  reasoning_tokens: number | null
  context_tokens: number | null
  token_quality: string
  user_preview: string | null
  assistant_preview: string | null
  raw_event_id: string | null
}

export interface ForensicSessionDetail {
  session: ForensicSession
  turns: ForensicTurn[]
  tools: Array<Record<string, unknown>>
  commands: Array<Record<string, unknown>>
  context_blocks: Array<Record<string, unknown>>
  file_accesses: Array<Record<string, unknown>>
  relationships: Array<Record<string, unknown>>
}

export interface ForensicTurnDetail {
  session: ForensicSession | null
  turn: ForensicTurn & { provenance_json: string | null }
  messages: Array<Record<string, unknown>>
  tools: Array<Record<string, unknown>>
  commands: Array<Record<string, unknown>>
  context_blocks: Array<Record<string, unknown>>
  file_accesses: Array<Record<string, unknown>>
  relationships: Array<Record<string, unknown>>
  raw_events: Array<Record<string, unknown>>
}

export interface ForensicHotspots {
  tools: Array<Record<string, unknown>>
  commands: Array<Record<string, unknown>>
  context: Array<Record<string, unknown>>
  files: Array<Record<string, unknown>>
}

export interface PaginatedForensicSessions {
  items: ForensicSession[]
  limit: number
  offset: number
  has_more: boolean
}

export function levelForPercent(pct: number | null, quality: DataQuality): UsageLevel {
  if (pct === null || quality === 'unavailable') return 'unknown'
  if (pct >= 100) return 'exhausted'
  if (pct >= 95) return 'critical'
  if (pct >= 80) return 'high'
  if (pct >= 50) return 'moderate'
  return 'normal'
}
