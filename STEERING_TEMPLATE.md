---
inclusion: auto
---

# Universal Coding Standards

## Communication Style

- Respond in Indonesian-English mix (same style as user)
- Be direct, concise, solution-oriented
- Explain reasoning before executing major changes
- Don't use monospace/code blocks for user-facing text (ugly in chat apps)
- Plain text preferred for readability

## Architecture Principles

- Clean Architecture when project structure supports it (domain → application → infrastructure → presentation)
- Separation of concerns — don't mix business logic with UI/framework code
- Repository pattern for data access
- Factory pattern for dependency injection
- Interface/ABC for abstractions that may have multiple implementations

## Coding Standards

### General

- Type hints on all functions (parameters + return)
- Async-first for I/O operations (HTTP, DB, file)
- Error handling: try-except around external calls, log real error, return user-friendly message
- No global mutable state for user-specific data — use proper state management (FSM, session, etc.)
- Constants at module top, not magic numbers in code

### Python Specific

- Use `int` for money (never `float`)
- Use dataclasses or Pydantic for structured data
- Prefer f-string over .format() or %
- Use logging module (not print)
- Async libraries only: httpx (not requests), asyncpg (not psycopg2), aiofiles (not open)

### Database

- Atomic operations for concurrent-sensitive data (balance, stock, counters)
- Use FOR UPDATE SKIP LOCKED for queue-like patterns
- Parameterized queries always — never f-string SQL values
- Migrations numbered sequentially, idempotent where possible

### Security

- Never hardcode secrets — use environment variables
- Never display secret values in responses (mask or reference by key name)
- Validate all user input before processing
- Rate limit where applicable

## Git Conventions

### Commit Messages

Format: `type: short description`

Types: feat, fix, refactor, chore, docs, test

Examples:

- feat: add multi-gateway payment support
- fix: prevent double-click duplicate orders
- refactor: extract broadcast logic to service layer
- chore: update dependencies, clean unused imports

### Branching

- Push to new branch for PRs, or direct to main for solo projects
- Never force push to shared branches

## Deployment

- Test locally before deploying
- Use systemd (Linux) for production services — auto-restart on crash
- Nginx as reverse proxy + SSL termination
- Environment-based config: ENVIRONMENT=development vs production
- .env files never committed to git

## Problem Solving Approach

1. Read relevant code before making changes
2. Understand the existing pattern, match it
3. If approach fails twice, step back and try fundamentally different approach
4. Verify changes compile/run before presenting
5. Don't add unnecessary abstractions — solve the actual problem
6. Don't refactor working code unless asked
7. Prefer minimal changes that solve the issue over large rewrites
