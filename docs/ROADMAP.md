# SocialScope practical improvement guide

This is a proposed sequence, not implemented scope. Start with observed researcher problems; do not turn the pilot into a general SaaS before validating its usefulness. The [handbook](HANDBOOK.md) explains today's implementation and the [feasibility report](COLLECTION_FEASIBILITY.md) separates historical-search evidence from assumptions.

## Assumptions that must change before shared hosting

| Local pilot assumption | Why it is acceptable locally | Required change for shared hosting |
|---|---|---|
| Individual member/admin accounts and organization sharing | Accounts can be provisioned later with admin oversight | Validate isolation on PostgreSQL; add project grants only if private projects are needed |
| Provider keys in a private .env | Simple administrator-managed installation | Central secret storage with access/rotation/audit procedures |
| Each install enforces its own pull limits | Limits one test workflow | Shared provider-account and workspace ceilings across all users/processes |
| Process-local provider rate controls, one worker | Keeps one process's activity predictable | Distributed account-level rate/concurrency control before adding workers |
| HTTP bound to loopback | No direct public service exposure | TLS reverse proxy, trusted origins, secure sessions, security updates |
| Manual backup and small synchronous exports | Low local volume | Scheduled verified backups, recovery objectives, asynchronous large exports |
| No per-user financial ownership | Pilot owner provides the accounts | User/project/workspace quotas and accountable attribution |
| Browser token in local storage | Preserved local session behavior | Review XSS/session threat model; consider secure HttpOnly sessions |

## 1. Improvements driven by pilot feedback

### Setup and onboarding

**Problem and trigger:** researchers cannot get a first empty project working or mistake missing credentials for no matches. Prioritize this if setup dominates feedback. **Change:** `scripts/setup.py`, `START_HERE.md`, source availability, and dashboard messages. Add a read-only diagnostic bundle with version/build, configured-source booleans, service readiness, and run IDs. **Dependencies/tradeoffs:** diagnostics must exclude keys, tokens, request headers, and raw research text by default. Avoid introducing telemetry just to collect feedback. **Validation:** observe two fresh installations without developer intervention, then inspect a diagnostic bundle for secrets and unnecessary data.

### Relevance, scope, and reversible decisions

**Problem and trigger:** researchers repeatedly retype filters or cannot explain why records were excluded. **Change:** Results filters, `PostService`, and NormalizedPost exclusion modeling. Add saved filter presets and optional exclusion reason/actor/time if users need an audit trail. **Dependencies/tradeoffs:** an immutable decision table is more work than the current boolean, but supports reproducibility. Clarify whether analytics uses current decisions or a frozen dataset version. **Validation:** reproduce a researcher's export from saved settings and test that restoring a post does not erase decision history.

### Better historical-source choices

**Problem and trigger:** approved benchmarks show weak unique historical yield or poor relevance. **Change:** adapter routing and Collections, after evidence review. Compare current Instagram Xpoz behavior with SociaVault popular/hashtag routes; compare Facebook discovery with researcher-supplied groups/pages; evaluate approved TikTok query variations. **Dependencies/tradeoffs:** source selection and query expansion change the research frame and cost. Record them explicitly; do not silently broaden searches. **Validation:** use the fixed benchmark cells, deduplicate against the baseline, manually assess incremental relevance, and report cost per additional relevant in-period observation.

### Progress and usable outcomes

**Problem and trigger:** users cannot tell whether a run is stalled, budget-limited, or finished with partial data. **Change:** platform progress events, `platform_collection.py`, Collections history, and accessibility of messages. Add consistent source-specific outcome codes if existing details prove too difficult to interpret. **Dependencies/tradeoffs:** frequent progress writes can increase database load; aggregate events without concealing long waits. **Validation:** scripted empty, missing-key, timeout, repeated-cursor, cancellation, and budget-stop scenarios must give different understandable messages.

### Dataset reproducibility and imports

**Problem and trigger:** researchers compare their other tool's X/Reddit/YouTube outputs or need a stable analysis release. **Change:** a separately designed import service and provenance source type; possibly dataset snapshots. **Dependencies/tradeoffs:** validate schemas, retain original identifiers, distinguish imported from vendor-observed timestamps, and avoid treating duplicates as independent observations. CSV formula safety applies on export. **Validation:** import the same file twice without duplicates; preserve run/source metadata; explain differences between imported and collected counts. No new import route is implemented now.

## 2. Preparing for one shared VM

### Deployment, TLS, and dependency maintenance

**Problem and trigger:** access moves beyond one person's localhost. **Change:** Compose/deployment packaging, reverse proxy, CORS, auth/session configuration, and dependency pins. Build versioned images, terminate TLS, keep PostgreSQL/Redis private, and run current dependency/security review before public exposure. **Dependencies/tradeoffs:** a VM is simpler than a cluster but has a single-host failure domain. Preserve staged rollout and rollback with tested schema compatibility. **Validation:** external connectivity/security checks, successful login through HTTPS, inaccessible database/broker ports, and rollback rehearsal without data loss.

### Centralized credentials and account caps

**Problem and trigger:** multiple researchers spend from the same owner account. **Change:** replace environment-only key ownership with ProviderAccount records/references to protected secrets; extend `BudgetContext.reserve` to check account/workspace/pull ceilings in one transaction. **Dependencies/tradeoffs:** different providers use different credit units, renewal periods, and billing semantics. Never add incomparable credits into one number. Require reliable cost bounds for any hard cap; leave unsupported paths blocked or separately controlled. **Validation:** races across users/projects must obey all applicable ceilings, with retry/timeout/crash cases and provider-price-change handling.

### Migrations, backups, and recovery

**Problem and trigger:** VM data becomes shared research work. **Change:** deployment runbook, migration pipeline, backup jobs, export storage policy, and restore checks. Define acceptable data loss (RPO) and recovery time (RTO) with the group. Encrypt backups, keep copies off the VM, and back up database plus export artifacts/config references. **Dependencies/tradeoffs:** restoring one without the other may leave missing files or stale paths. Destructive migrations need explicit backup/compatibility plans. **Validation:** restore into a separate instance and compare projects, ledger totals, memberships, export downloads, and login behavior; measure actual recovery time.

### Usage monitoring and alerts

**Problem and trigger:** an owner cannot watch each pull or detect stuck/spending-heavy workflows manually. **Change:** structured usage events, aggregate queries, admin dashboard, and operational alerts. Monitor unknown usage, cost-policy drift, queued/run age, source error rates, remaining account allowance, disk, backups, and worker health. **Dependencies/tradeoffs:** avoid logging credentials or unnecessary post contents. Alerts need an accountable recipient and actionable thresholds. **Validation:** induce one failure of each alert type in staging and verify diagnosis from sanitized IDs and metrics.

### Close the commit/publish gap

**Problem and trigger:** queued jobs occasionally never reach workers or reliable unattended use becomes necessary. **Change:** `SearchService.create_job`, a transactional outbox table, and a dispatcher task/process. Write the outbox entry with the run transaction; publish with a stable task ID; mark dispatch separately. **Dependencies/tradeoffs:** delivery remains at least once, so worker claims and database idempotency stay necessary. **Validation:** kill the publisher before and after broker acknowledgment; each job must eventually dispatch without duplicate active execution or fresh budget creation.

## 3. Supporting multiple researchers safely

### Account provisioning and project access

**Problem and trigger:** people should not read or delete every project in an organization. **Change:** user management, project membership/role tables, centralized access checks, routes/services, and UI. Support invitations or managed provisioning and revoke access predictably. **Dependencies/tradeoffs:** sharing semantics affect exports, authors, run history, and deletion. Review globally shared Account rows before claiming tenant isolation. **Validation:** a complete cross-user/cross-project access matrix, including direct API calls and export download URLs; UI hiding is insufficient.

### User/project credit allowances and atomic hierarchy

**Problem and trigger:** one researcher can exhaust a shared account by opening many pulls. **Change:** ledger attribution and reservation policy. Check user, project, workspace, provider-account, and pull limits atomically in a consistent lock order; reserve before network access; keep ambiguous usage debited. **Dependencies/tradeoffs:** monthly budgets need timezone/renewal rules and historical ledger integrity. Administrative adjustments should be auditable entries rather than overwriting old usage. **Validation:** concurrency tests across quota boundaries and renewal windows, retries, cancellations, and deliberate new-pull attempts to bypass quotas.

### Distributed provider rate limiting

**Problem and trigger:** more than one worker/process/VM uses an account. **Change:** replace process-local sliding windows/semaphores in `provider_limits.py` with account-keyed Redis coordination or another shared limiter. Keep budget authorization in its durable system. **Dependencies/tradeoffs:** limiter failure should fail closed for paid operations; lease expiry and crashed workers need careful handling. A rate limit controls timing, not spending. **Validation:** simultaneous workers honor requests/window and concurrency ceilings, including process crashes, lease expiration, and Redis unavailability.

### Queue fairness and concurrency

**Problem and trigger:** one user's large run blocks others or creates too much source contention. **Change:** dispatch policy, queues, worker configuration, and potentially per-platform tasks. Apply per-user/project active-run limits and fair scheduling before increasing concurrency. **Dependencies/tradeoffs:** splitting platform tasks improves scheduling but complicates finalization, cancellation, and usage aggregation. **Validation:** mixed small/large workloads show bounded queue delay, no starvation, no budget overshoot, and correct cancellation across tasks. Measure before adopting priority queues or specialized worker pools.

### Retention, deletion, and access lifecycle

**Problem and trigger:** projects accumulate raw cached responses/exports or people leave the group. **Change:** retention jobs, project deletion service, access revocation, ProviderCache TTL cleanup, and audit policy. Cancel and settle active jobs before deletion; define whether usage records must survive as an anonymized financial audit. **Dependencies/tradeoffs:** current project cascades are simple but delete usage context; deleting a project during active remote work can race persistence. Backups and downloaded CSVs require their own retention policies. **Validation:** deletion during queued/running/exporting states, expiry cleanup, revoked downloads, and retention reports. Never promise removal of files already downloaded to another machine.

## 4. Scale further only when justified

### Durable collection checkpoints

**Problem and trigger:** measured crash losses or long platform runs justify resumability. **Change:** per-page normalization/persistence, stable checkpoint/cursor records, SDK operation IDs where supported, and worker orchestration. **Dependencies/tradeoffs:** the checkpoint must advance atomically with accepted observations, while reservation state remains separate. Resuming historical pagination must not accidentally expand approved scope. **Validation:** crash at every boundary?before request, after charge, after response, after insertion, before cursor advance?and prove idempotent storage and conservative billing.

### Database and export performance

**Problem and trigger:** measured project size makes analytics or export slow. **Change:** query plans/indexes, server-side aggregate queries, streamed CSV generation, queued exports, and object storage with scoped download access. **Dependencies/tradeoffs:** current analytics loads records into Python; projects may exceed 5,000 across pulls. Materialized summaries need invalidation after exclusions. **Validation:** representative datasets, latency/memory measurements, inclusion changes, and export equivalence. Do not add partitioning, a warehouse, or a search cluster without evidence.

### Provider reliability and research APIs

**Problem and trigger:** fixed benchmarks show source coverage is inadequate for the actual questions. **Change:** provider contract/policy review and adapter/import boundaries. Consider eligible academic research APIs and researcher-owned exports, not extra sources purely to raise counts. **Dependencies/tradeoffs:** approval, geographic/institutional eligibility, permitted data use, lag, field coverage, and quotas vary. A new provider is not automatically more historically complete. **Validation:** the same benchmark matrix, documented sampling frame, account-level cost guard, and manual relevance/coverage audit before changing defaults.

### More infrastructure

**Problem and trigger:** one VM demonstrably cannot meet recovery or measured throughput requirements. **Change:** managed PostgreSQL/Redis, separate workers, object storage, deployment automation, and eventually multiple hosts. **Dependencies/tradeoffs:** every extra service adds cost, credentials, failure modes, and on-call work. Distributed locks, shared budgets, access controls, and backups must already exist. **Validation:** load and failure tests tied to explicit requirements; record actual throughput/recovery rather than assuming orchestration software creates reliability.

## Suggested gates

First finish a clean-stack migration/build/browser smoke test. Then collect feedback from a few supervised researchers with small allowances. Approve a separate historical-yield benchmark only after choosing monetary/account bounds, especially for Xpoz. Move to a shared VM only after access, central budget/rate controls, TLS, and restore validation. Scale further when measurements?not ambition alone?justify the next component.

## Implemented account preparation ? 2026-10-26

Individual member creation, enable/disable controls, safe initial admin provisioning and operator password reset, organization-scoped per-person activity, and a simple private feedback inbox are implemented. Seed no longer overwrites existing users. Intended Markdown documentation is allowlisted for version control; other documentation artifacts remain ignored.

No real pilot accounts have been added. Public signup, email invitations/recovery, cross-organization owner dashboards, private per-person projects, distributed provider limits, production hosting, and live concurrent-user validation are not part of this change. Earlier roadmap proposals remain proposals unless explicitly identified here or in the changelog.
