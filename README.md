# Dynamic Prefab UI Database Chat

Streamlit app that connects to either synthetic demo data or a configured MySQL database, uses Claude to plan safe read-only SQL, and renders validated dynamic UI with Prefab components.

## Where It Helps

This app is useful when a team wants to explore a relational database without building a fixed dashboard for every question. A user can ask plain-English questions, the app inspects the live schema, runs validated read-only SQL, and chooses a fitting UI such as a table, KPI cards, charts, detail views, filters, or schema relationship views.

It works well for internal analytics demos, database discovery, quick operational reporting, and prototyping dynamic data apps where the UI should adapt to the result shape instead of being hardcoded for one business domain.

## Setup

```bash
uv sync
cp .env.example .env
```

For a demo without a real database, keep `DEMO_MODE=true` in `.env`. The app will create a synthetic SQLite database with generic customers, loan products, loan accounts, payments, and fees.

For a live database, set `DEMO_MODE=false` and fill `.env` with read-only MySQL credentials and an Anthropic API key. `.env` is ignored by Git.

## Run

```bash
uv run streamlit run main.py
```

Runtime files, generated Prefab output, caches, local environments, and secrets are excluded from the repository.

## Demo Video
https://youtu.be/b5juBM40FGw
