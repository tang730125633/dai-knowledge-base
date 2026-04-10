# OpenClaw Config Snapshot

- Snapshot: `xiaolin-main-2026-04-10-1752`
- Generated from: `/Users/mf/.openclaw`
- Purpose: compare this host with XiaoTing without exposing live secrets.
- Sensitive values replaced with `<REDACTED>`.

## Key Highlights

- Primary model: `google/gemini-3-flash-preview`
- Fallback count: `4`
- Image model: `google/gemini-2.5-flash-image`
- Memory backend: `qmd`
- Memory search mode: `search`
- Providers in `models.json`: `arcee, google-vertex, kimi, kimi-coding, moonshot, ollama, openai-codex, openrouter, zai`
- Auth profiles: `anthropic:111, anthropic:default, google-vertex:default, google:default, kimi-coding:default, moonshot:default, openai-codex:default, openrouter:default, zai:default`

## Channels

- WeCom enabled: `false`
- Feishu enabled: `true`
- Feishu require mention: `false`

## Cron Jobs

- `零碳能源早报` | enabled=`true` | expr=`30 10 * * *` | tz=`Asia/Shanghai`
- `能源行业日报` | enabled=`false` | expr=`30 8 * * *` | tz=`Asia/Shanghai`
- `小琪刷牙提醒` | enabled=`true` | expr=`0 9 * * *` | tz=`Asia/Shanghai`
- `openclaw_watchdog_every30min` | enabled=`true` | expr=`*/30 * * * *` | tz=`Asia/Shanghai`
- `dai_enterprise_comprehensive_report_6h` | enabled=`true` | expr=`0 0,6,12,18 * * *` | tz=`Asia/Shanghai`

## File Map

- `openclaw.redacted.json` <- `~/.openclaw/openclaw.json`
- `auth-profiles.redacted.json` <- `~/.openclaw/agents/main/agent/auth-profiles.json`
- `models.redacted.json` <- `~/.openclaw/agents/main/agent/models.json`
- `cron-jobs.redacted.json` <- `~/.openclaw/cron/jobs.json`
- `devices-paired.redacted.json` <- `~/.openclaw/devices/paired.json`
- `devices-pending.redacted.json` <- `~/.openclaw/devices/pending.json`
- `wecom-config.redacted.json` <- `~/.openclaw/wecomConfig/config.json`
- `manifest.json` <- snapshot metadata and redaction rules

## Excluded On Purpose

- `*.bak*` backup files
- Session history dumps under `agents/main/sessions/`
- Redundant installers or temporary scripts
