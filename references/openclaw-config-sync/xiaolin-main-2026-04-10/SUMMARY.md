# OpenClaw Config Snapshot

- Snapshot: `xiaolin-main-2026-04-10`
- Generated from: `/Users/mf/.openclaw`
- Purpose: compare this host with XiaoTing without exposing live secrets.
- Sensitive values replaced with `<REDACTED>`.

## Key Highlights

- Primary model: `google/gemini-3.1-pro-preview`
- Fallback count: `4`
- Image model: `google/gemini-2.5-flash-image`
- Memory backend: `qmd`
- Memory search mode: `search`
- Providers in `models.json`: `ollama, moonshot, kimi-coding, zai, google-vertex, openrouter, kimi, openai-codex, arcee`
- Auth profiles: `moonshot:default, kimi-coding:default, zai:default, openrouter:default, google-vertex:default, anthropic:111, anthropic:default, google:default, openai-codex:default`

## Channels

- WeCom enabled: `False`
- Feishu enabled: `True`
- Feishu require mention: `False`

## Cron Jobs

- `零碳能源早报` | enabled=`True` | expr=`30 10 * * *` | tz=`Asia/Shanghai`
- `能源行业日报` | enabled=`False` | expr=`30 8 * * *` | tz=`Asia/Shanghai`
- `小琪刷牙提醒` | enabled=`True` | expr=`0 9 * * *` | tz=`Asia/Shanghai`
- `openclaw_watchdog_every30min` | enabled=`True` | expr=`*/30 * * * *` | tz=`Asia/Shanghai`
- `dai_enterprise_comprehensive_report_6h` | enabled=`True` | expr=`0 0,6,12,18 * * *` | tz=`Asia/Shanghai`

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
