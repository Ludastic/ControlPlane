# Control Plane Roadmap

## 1. MVP Completion

- Make database-backed repositories the primary persistence path.
- Replace mocked desired state composition with real assembly from assignments, memberships, resources, and artifacts.
- Replace mocked effective policies calculation with real scope/priority-based evaluation.
- Move artifact handling from in-memory bytes to external file storage with metadata in the database.
- Keep memory backend only for isolated tests or remove it after DB stabilization.

## 2. Production Readiness

- Implement admin authentication with stored users, password hashing, JWT access/refresh tokens, and RBAC.
- Implement agent bootstrap and token lifecycle with secure storage of token hashes.
- Add full execution run persistence, idempotent event ingestion, and richer status queries.
- Add inventory retention/history policy and normalized queries where needed.
- Make database migrations the only supported schema management path.

## 3. Hardening

- Add conflict detection for equal-scope/equal-priority configuration overlaps.
- Add structured logging, audit coverage, readiness checks, and CI migration validation.
- Add PostgreSQL-first integration tests and phase out SQLite-specific assumptions where possible.
- Add artifact checksum validation, storage abstraction, and operational cleanup jobs.

## Current Focus

The current implementation phase is shifting from core hardening into operational polish: broader deployment ergonomics and production-facing configuration cleanup.
