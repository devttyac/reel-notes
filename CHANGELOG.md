# Changelog

## v0.1.2 — 2026-05-03

Fix Claude Code sandbox compatibility — v0.1.1 was unusable under Claude Code because its sandbox injects an empty `ANTHROPIC_API_KEY` into all child processes, silently overwriting the user's real key.

- Add `SUMTUBE_API_KEY` as the preferred env var name under Claude Code (sandbox does not overwrite this name).
- Lookup order in `summarize.py` is now: `--api-key` flag → `SUMTUBE_API_KEY` → `ANTHROPIC_API_KEY`.
- Load `.env` from plugin root (`plugins/sumtube/.env`) via `python-dotenv`; both var names are read.
- Add `plugins/sumtube/.env.example` documenting the variables.
- `setup.py --check` accepts either `SUMTUBE_API_KEY` or `ANTHROPIC_API_KEY` and reads `.env`.
- Update README (root + sumtube) to document Claude Code sandbox workaround and `.env` flow.

## v0.1.1 — 2026-05-03

Marketplace install fixes — v0.1.0 was uninstallable in Claude Code. v0.1.1 makes the documented install flow work end-to-end.

- Add required `name` and `owner` fields to `.claude-plugin/marketplace.json`; rename `path` → `source`; drop redundant `skills` array (auto-discovered).
- Add per-plugin `.claude-plugin/plugin.json` manifests for `sumtube` and `media-downloader` (previously missing — caused install failure).
- Move each plugin's `SKILL.md` into `skills/<name>/SKILL.md` to match Claude Code's auto-discovery convention.
- Fix `hooks.json` schema in both plugins: nested `hooks` array structure, and replace hardcoded `plugins/<name>/...` paths with `${CLAUDE_PLUGIN_ROOT}` for portability.
- Update README install instructions (root + both plugins) to use the marketplace flow: `claude plugin marketplace add .` then `claude plugin install <plugin>@reel-notes`.

## v0.1.0 — 2026-05-03

- Initial public release: `sumtube` and `media-downloader` plugins for Claude Code, with a two-step download-then-summarise workflow supporting YouTube and 1,000+ yt-dlp sources.
