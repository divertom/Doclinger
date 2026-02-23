# Contributing to Docling-UI

Thank you for your interest in contributing.

## How to contribute

1. **Open an issue** — For bugs, feature ideas, or questions, open a [GitHub Issue](https://github.com/divertom/docling-ui/issues).
2. **Fork and clone** — Fork the repo and clone your fork locally.
3. **Create a branch** — Use a short branch name, e.g. `fix/upload-error` or `docs/readme`.
4. **Make your changes** — Follow the existing code style. Run tests before submitting:
   ```bash
   cd backend && pytest
   ```
5. **Submit a pull request** — Target the `master` branch. Describe what you changed and why.

## Development setup

See the [README](README.md) for local run instructions (venv, backend, UI). For Docker, use the dev profile if you want backend and UI in separate containers.

## Code and docs

- Backend: Python 3.11+, FastAPI, Pydantic.
- UI: Streamlit.
- Keep the README and docstrings accurate when you change behavior.

If you have questions, open an issue and we can discuss.
