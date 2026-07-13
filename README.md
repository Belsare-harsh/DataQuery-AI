# Dataquery AI

A conversational SQL analyst assistant that lets you ask business questions in plain English and get real answers straight from your Postgres database — no SQL knowledge required.

## What it does

Dataquery AI sits on top of a business database (revenue, subscriptions, product usage, customer support, and per-user "360" data) and answers natural language questions like:

- "What's our MRR right now?"
- "How many open support tickets do we have?"
- "What's the average revenue per partner over the last 3 months?"
- "Show me user 1042's activity and open tickets"

Behind the scenes, it translates each question into a safe, read-only SQL query, runs it against the live database, and responds with a concise, human-readable answer — formatted in local currency, with the relevant table/time period cited for clarity.

## How it works

- **LLM-powered query generation** — a language model (via Groq) interprets the question and writes the corresponding SQL, guided by a detailed system prompt covering table structure, business terminology, and date-handling conventions.
- **Read-only by design** — every query is parsed and validated before execution to ensure only `SELECT`/`WITH` statements run; no inserts, updates, deletes, or schema changes are ever possible through the assistant.
- **Smart table routing** — a core set of frequently used tables (revenue, subscriptions, support, product usage) is always available to the model. For less common data — deep per-user detail, extended engagement metrics — the assistant looks up the exact schema on demand instead of carrying the full database structure in every request, keeping responses fast and efficient.
- **Ambiguity handling** — vague or underspecified questions (e.g. "top users," "doing well," a month without a year) prompt the assistant to clarify its interpretation before answering, rather than guessing.
- **Built with Flowise** — the conversational agent, memory, and tool orchestration are assembled visually using Flowise, backed by a lightweight API layer that executes queries safely against the database.

## Data coverage

The assistant can answer questions across:
- **Revenue & Subscriptions** — MRR, ARPU, plan distribution, renewals, upgrades, conversions
- **Product Usage** — DAU/WAU/MAU, engagement, retention, feature and content usage
- **Customer Support** — ticket volume, resolution times, SLA breaches, agent workload
- **User 360** — per-user activity, revenue history, and support history

## Status

Actively being refined — current focus areas include tightening ambiguity handling for time-based questions, expanding schema coverage, and optimizing token usage in longer conversations.
