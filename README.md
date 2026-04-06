<p align="center">
  <img src="docs/screenshots/nio-avatar.png" alt="NIO" width="128" style="image-rendering: pixelated;" />
</p>

<h1 align="center">NIO</h1>

<p align="center">
  <strong>voice DNA. semver souls. anti-slop. the layer hermes never had.</strong>
</p>

<p align="center">
  <a href="#install">Install</a> &bull;
  <a href="#what-nio-adds">Features</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#souls">Souls</a> &bull;
  <a href="#anti-slop">Anti-Slop</a> &bull;
  <a href="#team-mode">Teams</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-4EC373?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/license-MIT-4EC373?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/hermes-plugin-4EC373?style=flat-square" alt="Hermes Plugin" />
  <img src="https://img.shields.io/badge/dashboard-localhost:4242-4EC373?style=flat-square" alt="Dashboard" />
</p>

---

<p align="center">
  <img src="docs/screenshots/nio-boot.gif" alt="NIO Boot Sequence" width="480" />
</p>

<details>
<summary>Architecture diagram</summary>

<p align="center">
  <img src="docs/screenshots/nio-hero.svg" alt="NIO Architecture" width="800" />
</p>

</details>

---

## Install

```bash
curl -sSf https://nio.sh | bash
```

Or with pip:

```bash
pip install nio-agent
nio install
```

Then run the setup wizard:

```bash
nio setup
```

Walks you through mode selection (global vs team), platform connections (Discord, Telegram, WhatsApp, Slack, Signal), memory import, and verification. Dashboard starts at `localhost:4242`.

## What NIO adds

NIO is a superset of [Hermes Agent](https://github.com/NousResearch/hermes-agent). Hermes gives you the runtime. NIO gives you everything else.

```
                    Hermes          NIO
                    ──────          ───
gateway             yes             yes (via hermes)
CLI + TUI           yes             yes (via hermes)
memory              yes             yes + team-shared
voice DNA           no              yes (runtime enforcement)
anti-slop           no              yes (29 patterns, 3 tiers)
soul versioning     no              yes (semver, diff, rollback)
metrics             no              yes (slop, latency, signals)
dashboard           no              yes (localhost:4242, autostart)
team mode           no              yes (signed souls, git memory)
claude code         no              yes (skill + hooks)
```

Zero patches to the Nous Research fork. NIO installs as a Hermes plugin at `~/.hermes/hooks/nio/`.

## Quick start

```bash
# what's running
nio status

# switch souls
nio soul apply nio-core

# check anti-slop score on a file
nio antislop check draft.md

# score inline text
nio antislop score "The uncomfortable truth is this game changer unleashes chaos."
# -> 12/100 (4 violations: authority_signaling, hype_words x3)

# open the dashboard
nio dash

# release a new soul version after tuning
nio soul release nio-core --bump minor --message "tightened slop floor to 95"

# diff two soul versions with metric deltas
nio soul diff nio-core@0.1.0 nio-core@0.2.0
```

## Architecture

Every outbound agent message passes through NIO middleware:

```
hermes gateway                    claude code
      |                                |
      v                                v
  ~/.hermes/hooks/nio/         ~/.claude/skills/nio/
      |                                |
      +──────────────┬─────────────────+
                     |
              NIO middleware
              |    |    |    |
              v    v    v    v
           soul  voice  slop  metrics
              |    |    |    |
              v    v    v    v
           ~/.nio/nio.db (SQLite + WAL)
                     |
                     v
              localhost:4242
              (FastAPI + HTMX)
```

**5-event pipeline:**

| Event | What happens |
|---|---|
| `gateway:startup` | Init DB, load active soul + voice |
| `session:start` | Resolve soul (team-aware by cwd), inject prompts |
| `agent:start` | Record user message, start latency timer |
| `agent:end` | Apply voice, score slop, record turn, emit to dashboard |
| `command:*` | Handle `/nio-status`, `/nio-soul`, `/nio-dash` |

## Souls

Markdown + YAML frontmatter. Human-editable. Version-controlled. Diffable.

```yaml
---
soul: nio-core
version: 0.2.0
voice: shawn-builder@1.0.0
targets:
  slop_score_floor: 92
  latency_p50_ms: 2000
antislop:
  profile: strict
---

# NIO Core

[prompt body loaded verbatim into the system prompt]
```

Version your souls like software:

```bash
nio soul release nio-core --bump minor --message "tightened slop floor"
nio soul diff nio-core@0.1.0 nio-core@0.2.0
nio soul checkout nio-core@0.1.0
```

`nio soul diff` shows the prompt body diff alongside metric deltas (slop avg, p50 latency, user signal, session count) between versions.

Souls support inheritance via `derived_from`. Child soul merges voice, anti-slop overrides, targets, and prompt body from parent. Cycles detected and rejected.

**Starter souls:** `nio-core` (daily driver) and `nio-reviewer` (PR review + anti-slop enforcer).

## Anti-Slop

Single JSON registry at `registry/anti-slop.json`. 29 patterns across three tiers:

| Tier | Count | Weight | Examples |
|---|---|---|---|
| **critical** | 20 | 3x | em-dashes, authority signaling, hype words, sycophantic openers |
| **context** | 5 | 1.5x | engagement bait, false dichotomies (OK in some contexts) |
| **natural** | 4 | 0x | ellipses, arrows, emoji markers (your actual voice, not slop) |

**Score formula:**

```
score = 100 - sum(severity * tier_weight * count) / tokens * 100
clamped [0, 100]
```

One registry generates validators for both languages:

```bash
nio antislop sync
# -> nio/core/antislop.py        (Python, baked-in rules)
# -> treadit/src/lib/ai/anti-slop.ts  (TypeScript, full module)
# -> docs/anti-slop-reference.md      (human-readable)
```

No more drift between implementations.

## Voice DNA

Voice profiles define tone, banned phrases, anti-slop rule subsets, and formatting rules. Independent from souls. Souls pin a voice at a specific version.

**Included profiles:**
- `shawn-builder` . builder-first, casual competence, SDR-to-GTME arc
- `enterprise-neutral` . professional, clean, no personal brand elements

```bash
nio voice apply shawn-builder
nio voice diff shawn-builder@1.0.0 shawn-builder@1.1.0
```

Runtime `apply()` runs on every outbound message:
1. Hard reject on banned phrases
2. Anti-slop validation with the voice's rule set
3. Preferred phrasing advisories (to dashboard, not inline edits)

## Dashboard

`localhost:4242`. Autostarted via launchd on install. Dark theme. Big numbers.

**Panels:**
- **Now Playing** . active soul, voice, live slop gauge, recent turns with inline violations
- **Soul Diff** . side-by-side prompt diff + metric deltas between versions
- **Metrics** . slop scores by version, latency time series, task distribution
- **Team Activity** . per-member rollup, version adoption, slop leaderboard
- **Registry** . browsable souls, voices, anti-slop rules
- **Gateway Status** . Hermes connectivity grid

Stack: FastAPI + HTMX + Alpine + Chart.js. No npm build step.

## Team mode

Drop a `.nio/team.toml` in any repo:

```bash
nio team init --name my-team
# collaborators run:
nio team join github.com/org/repo
```

When a collaborator enters the repo directory, NIO auto-activates the team soul.

- **Signed souls** . signature verification, prompt injection detection
- **Git-backed memory** . shared context at `.nio/memory/`
- **Owner-controlled releases** . `nio team release` with permission enforcement
- **Trust model** . pin voice profiles, require signed soul bodies

## CLI

```
nio install [--migrate-hermes]
nio setup [mode|platforms|memory|verify]
nio status
nio doctor

nio soul list|show|create|edit|release|diff|checkout|apply|active
nio voice list|show|apply|diff|release
nio antislop check|score|sync|list
nio metrics show|export|team
nio team init|join|sync|members|release
nio dash [start|stop]
```

## Data

All runtime state lives at `~/.nio/`:

```
~/.nio/
  bin/nio          CLI symlink
  venv/            isolated Python environment
  nio.db           SQLite (sessions, turns, soul/voice versions, team state)
  config.yaml      dash port, autostart, telemetry opt-out
  active/          current soul.txt + voice.txt pointers
  teams/           joined team manifests
  logs/            dash stdout/stderr
```

Separate from Hermes state. Clean uninstall. Cross-DB queries via `ATTACH DATABASE` when needed.

## License

MIT

---

<p align="center">
  <sub>built by <a href="https://github.com/shawnla90">shawn</a> . made by pi</sub>
</p>
