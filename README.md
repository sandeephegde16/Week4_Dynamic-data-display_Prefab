# Dynamic Prefab UI Database Chat

Streamlit app that connects to a configured MySQL database, uses Claude to plan safe read-only SQL, and renders validated dynamic UI with Prefab components.

## Setup

```bash
uv sync
cp .env.example .env
```

Fill `.env` with read-only MySQL credentials and an Anthropic API key. `.env` is ignored by Git.

## Run

```bash
uv run streamlit run main.py
```

Runtime files, generated Prefab output, caches, local environments, and secrets are excluded from the repository.
