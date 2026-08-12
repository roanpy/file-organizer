# Contributing

## Before You Start

Please open an issue for behavior changes, matching-rule changes, new file-operation capabilities, or changes to the packaging contract. Small documentation and test fixes can go directly through a pull request.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The core application does not require Gemini, DeepSeek, Ollama, or LiteLLM SDKs. Use synthetic temporary directories for tests. Never commit real paths, provider keys, runtime logs, databases, or downloaded packages.

## AI-Assisted Development

The project is developed primarily with OpenAI Codex, with other AI coding agents and local agent workflows used for focused implementation, review, testing, documentation, and release checks. AI assistance does not replace human review: contributors must inspect changes, run the required checks, and confirm security and file-operation behavior before merging.

## Required Checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src SoftwareOrganizer-Skill tests
node --check static/app.js
node --check static/i18n.js
python scripts/check_public_safety.py
python -m pip check
```

Changes to matching, retention, transfer, deletion, configuration security, or AI fallback behavior must include a focused regression test. Destructive operations must keep the existing confirmation and configured-root safety checks.

## Pull Requests

- Explain the user-visible behavior and the reason for the change.
- Keep unrelated formatting and refactors out of the pull request.
- Use synthetic screenshots and paths only.
- Update the relevant README, changelog, or maintenance record when behavior or release requirements change.
