# Changelog

## [0.1.0] - 2026-04-06

Initial release.

### Added
- **Soul system**: Markdown + YAML frontmatter souls with semver versioning, inheritance, diff, rollback
- **Voice DNA**: Independent voice profiles with runtime enforcement (banned phrases, anti-slop, tone rules)
- **Anti-slop registry**: 29 patterns across 3 tiers. Single JSON source generates Python, TypeScript, and Markdown validators
- **Hermes bridge**: Zero-patch plugin at `~/.hermes/hooks/nio/`. 5-event middleware pipeline
- **Claude Code integration**: SKILL.md with inline soul rules, session bridge (`nio cc`), lifecycle hooks
- **Persistent memory**: SQLite-backed session resume chain. Memory bridge for Hermes and Claude handoffs
- **Dashboard**: FastAPI + HTMX at `localhost:4242` with 6 panels
- **Setup wizard**: 4-stage interactive setup (mode, platforms, memory, verify)
- **Team mode**: `.nio/team.toml` for shared souls, git-backed memory, mode-aware resolution
- **Metrics**: Per-turn slop scores, latency tracking, task-type classification, platform filtering
- **CLI**: `nio soul|voice|antislop|metrics|team|cc|dash|install|setup|status|doctor`
- **Boot animation**: DK-style terminal sequence with 429 barrel dodge and victory
- **GitHub Actions CI**: Python 3.11/3.12/3.13 matrix with pytest and ruff
- **141 tests** across 11 test modules (6 dashboard template tests skipped pending fix)

### Starter content
- `nio-core` soul (daily driver, builder-first)
- `nio-reviewer` soul (PR review, slop floor 95)
- `shawn-builder` voice profile
- `enterprise-neutral` voice profile
