# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Squire is a GitHub PR proxy that syncs PR data to a local SQLite database and lets AI agents submit code reviews via CLI. Reviews are stored locally — humans inspect them through a web dashboard and optionally publish to GitHub. Core principle: AI agents comment, humans approve.

## Architecture

```
GitHub → squire-engine (Python/FastAPI) → SQLite
                ↑                            ↑
           CLI (prx)  ←── AI agents     Web UI (React) ←── human reviewers
```

- **squire-engine/**: Python backend — CLI (`prx` commands), FastAPI server, SQLite storage. Managed with `uv`. Requires Python 3.13+.
- **squire-client/**: React + TypeScript frontend (Vite). Dashboard for reviewing AI-generated PR comments.
- **design.md**: Full system design document (in Korean) — authoritative source for data models, CLI interface, and API design.
- **docs/work-plan.md**: Implementation roadmap (Phases 0–3).

## Build & Dev Commands

### Frontend (`squire-client/`)

```bash
cd squire-client
npm install          # install dependencies
npm run dev          # Vite dev server with HMR
npm run build        # TypeScript check + production build
npm run lint         # ESLint
npm run preview      # serve production build locally
```

### Backend (`squire-engine/`)

Always use `uv`, never system Python/pip:

```bash
cd squire-engine
uv sync              # install/sync dependencies
uv run python main.py   # run entry point
```

## Coding Conventions

### Frontend (TypeScript/React)
- 2-space indentation, single quotes
- PascalCase for components (`PullRequestList.tsx`), camelCase for functions/variables, kebab-case for non-component files
- ESLint with typescript-eslint, react-hooks, and react-refresh rules (flat config in `eslint.config.js`)
- Strict TypeScript (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`)

### Backend (Python)
- PEP 8, 4-space indentation
- snake_case for functions/modules, PascalCase for classes

### Commits
- Format: `type(scope): short imperative summary` (e.g., `feat(engine): add prx sync command`)

## Current State

The project is in early development — no initial git commit yet. Frontend is Vite+React boilerplate; backend is a stub `main.py`. No tests, CI, or database schema implemented yet. Next step is Phase 0 (directory structure, config loader) then Phase 1 (MVP CLI with SQLite schema and `prx` commands).
