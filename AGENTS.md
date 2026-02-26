# Repository Guidelines

## Project Structure & Module Organization
This repository is split into two main modules:
- `squire-client/`: React + TypeScript frontend (Vite). App code is in `squire-client/src/`; static files are in `squire-client/public/`.
- `squire-engine/`: Python backend prototype. Current entry point is `squire-engine/main.py`; project metadata is in `squire-engine/pyproject.toml`.

Top-level docs live in `design.md`. Keep feature-specific docs near the code they describe.

## Build, Test, and Development Commands
Frontend (`squire-client`):
- `npm install`: install dependencies.
- `npm run dev`: start local Vite dev server with HMR.
- `npm run build`: run TypeScript build (`tsc -b`) and produce production bundle.
- `npm run lint`: run ESLint checks.
- `npm run preview`: serve built frontend locally.

Backend (`squire-engine`):
- `python main.py`: run the current backend stub.

## Coding Style & Naming Conventions
Frontend uses ESLint (`squire-client/eslint.config.js`) with TypeScript + React hooks rules.
- Use 2-space indentation in TS/TSX and follow existing single-quote style.
- Name React components in `PascalCase` (example: `PullRequestList.tsx`).
- Use `camelCase` for variables/functions and `kebab-case` for non-component asset filenames.

Backend Python should follow PEP 8:
- 4-space indentation.
- `snake_case` for functions/modules, `PascalCase` for classes.

## Testing Guidelines
No automated test framework is configured yet in either module. For new features:
- Add tests with the framework introduced in the same PR.
- Keep frontend tests near source (`src/`) or in `src/__tests__/`.
- Include manual verification steps in PR descriptions until automated tests are standard.

## Commit & Pull Request Guidelines
The repository has no commit history yet, so adopt this convention now:
- Commit format: `type(scope): short imperative summary` (for example, `feat(client): add PR list view`).
- Keep commits focused and atomic.

PRs should include:
- What changed and why.
- Linked issue/task (if available).
- How it was tested (`npm run lint`, manual flow, etc.).
- UI screenshots for frontend-visible changes.

## Security & Configuration Tips
- Do not commit secrets or tokens.
- Keep local env files untracked.
- If GitHub integration is added, prefer `GITHUB_TOKEN` via environment variables.
