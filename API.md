# SocialScope API, version 0.1.0

Interactive schema: `http://localhost:8002/api/docs`; JSON: `/api/openapi.json`. Except health, login, and query-limit metadata, application endpoints require `Authorization: Bearer <token>`. Examples use placeholders, never real credentials. The browser reaches `/api` through Next's proxy. The URLs here use default ports; [Ports and configuration](docs/PORTS_AND_CONFIGURATION.md) explains overrides. This reference was checked against the code on September 30, 2026; it does not assert that live provider behavior has been verified.

## Routes

| Method/path | Purpose |
|---|---|
| GET `/api/health` | Database/Redis health fields; inspect the JSON, not only HTTP status |
| POST `/api/auth/login` | JSON email/password -> bearer token |
| GET `/api/auth/me` | Current user |
| GET `/api/sources` | Configured-source booleans, providers, limitations, version/build |
| GET/POST `/api/projects` | List/create organization projects; create does not collect |
| GET/PATCH/DELETE `/api/projects/{project_id}` | Read/update/delete organization project; active runs block deletion with 409; deletion is permanent |
| POST `/api/projects/launch` | Retained create-plus-initial-job route; initial_job obeys the same safeguards |
| GET/POST `/api/projects/{project_id}/jobs` | Run history/create preview or full collection |
| GET `/api/projects/{project_id}/jobs/{job_id}` | Stored configuration, query version, progress, usage, preview examples |
| POST `/api/projects/{project_id}/jobs/{job_id}/cancel` | Cooperative cancellation |
| GET `/api/projects/{project_id}/posts` | Filtered project observations |
| PATCH `/api/projects/{project_id}/posts/{post_id}/exclusion` | Reversible inclusion state |
| GET `/api/projects/{project_id}/analytics/overview` | Included post/author/source/engagement counts and hashtags |
| GET `/api/projects/{project_id}/analytics/volume` | Publication-date volume; optional date filters |
| GET `/api/projects/{project_id}/analytics/platforms` | Included platform distribution |
| GET `/api/projects/{project_id}/analytics/wordmap` | Included text co-occurrence |
| GET/POST `/api/projects/{project_id}/exports` | List/create CSV exports |
| GET `/api/projects/{project_id}/exports/{export_id}/download` | Authenticated, ownership-checked download |
| GET `/api/dashboard/summary` | General project/run/post totals; `/stats` is compatibility alias |
| GET `/api/query-limits` | Query validation metadata |
| POST `/api/llm/generate-queries` | Retained optional query helper; not required by pilot collection UI |
| GET `/api/admin/overview`, `/api/admin/audit-log` | Admin-only credential presence and organization activity |

Recruitment, flag/suppress, routine post DELETE, enrichment, and paid analytics-summary routes are not active.

## Health and authentication

`GET /api/health` returns `status`, `database`, and `redis`. Healthy output is `{"status":"ok","database":true,"redis":true}`. A degraded result still returns HTTP 200, so callers must inspect these fields.

Login accepts `{"email":"<your email>","password":"<your password>"}` and returns `access_token` and `token_type`. Send the token in the Authorization header, never in a URL. Use the privately configured local login; do not put real credentials into examples or shared logs. Interactive API docs and OpenAPI metadata are also publicly readable locally.

Project PATCH currently accepts only `name`, `description`, `domain`, and `status`; it does not edit previous run settings or provide a general research-settings editor. Source/query/dates for collection belong to each new job.

## Create a project and preview

```json
{"name":"Transit accessibility","description":"Study discussion about access to public transport","research_question":"How do people describe transit barriers?"}
```

Send that body to POST /api/projects. Then send to its jobs route:

```json
{"name":"Transit search preview","mode":"preview","query":"public transit","platforms":["tiktok","twitter","reddit","youtube"],"date_from":"2026-08-01T00:00:00Z","date_to":"2026-08-31T23:59:59.999999Z","requested_post_count":500,"comparison_limit":8,"primary_credit_limit":20,"request_limit":20}
```

Creating a job can spend provider credits once a worker executes it; these examples are not offline checks. Set `mode` explicitly: it defaults to `collection`, not `preview`. The total target defaults to 500 when neither count input is provided.

Dates may be null/omitted. Naive dates become UTC; reversed dates fail. Sources are case-normalized, deduplicated, and limited to instagram/tiktok/facebook/twitter/reddit/youtube; x aliases twitter. Queries use existing provider-specific safeguards (default 200 characters). Target is 100-5,000 total, never per source; legacy max_results_per_platform input is treated as the fallback total target.

The response contains run `id`, `pull_id`, mode, status, platform allocations/states, original query_versions, total_posts_collected, usage, and preview_examples. Each new execution creates its own query version. Preview allocations are at most 20 per platform. A matching completed preview is reused within 900 seconds for the same pull/configuration.

## Continue a pull

Include the returned pull_id in subsequent preview revisions or the full collection. Keep selected sources unchanged. Set mode=collection to collect within the same allowance. One active run is allowed per pull and at most one full run. After a full run is created, that pull accepts no further previews or collections, even if the run fails or is cancelled. Conflicts return 409; changing sources returns 422. Pull limits are fixed on creation, even if new values are sent later. Omitting pull_id starts a **new** allowance; APIs do not infer relatedness from query text.

Comparison sources share 5-8 credits total (default/max eight). Predictable integer shares follow X, Reddit, YouTube order; unused shares do not transfer. Primary SociaVault credit limit defaults to 20, range 1-100 per primary source. Request limit defaults to 20, range 1-100 per source for the entire pull. Each preview additionally has a small attempt limit: one normally, two Facebook, three Instagram outer SDK operations. Retries count. No more than 5,000 unique stored identities are accepted across all previews/revisions/full runs within a pull.

Usage is **cumulative for the pull**, not isolated to the displayed run. Per-platform fields include requests, reserved (unsettled reservations), estimated, reported, unknown_requests, charged_allowance, credit_limit, and credits_bounded. Do not sum usage snapshots from multiple runs. Ambiguous usage remains debited. Instagram has credits_bounded=false; operation counts are not a claimed credit ceiling. Unknown SociaVault endpoint costs fail closed.

Status: pending, queued, running, cancelling, completed, completed_with_errors, cancelled, failed. Platform details distinguish provider stop reason, error, observed publication bounds, and available duplicate/out-of-range/page metrics. A successful POST is not proof of successful collection. Remote work already submitted may continue after cancellation.

## Results, exclusion, and export

GET posts accepts repeated platform values, date_from/date_to, search, sort_by (date/oldest/engagement/most_engaged), scope (included default/excluded/all), optional run_id, page>=1, and per_page 1-100. Records are deduplicated per project/platform/external ID; RunPost preserves encounters. A project can exceed 5,000 posts through multiple explicit pulls.

Exclusion body: `{"excluded":true}`. Restore with false. This changes the project observation only and does not delete provenance. Descriptive analytics always uses included records.

CSV is the implemented export format; use `format: "csv"` (the schema does not currently reject every other string). Export body: `{"format":"csv","scope":"included"}` plus optional platform array/date_from/date_to/search. Generation is currently synchronous; the returned ExportJob can already be completed or failed. CSV retains basic post/author/engagement/link fields and adds provider, collected_at, excluded, analysis_scope, collection_context JSON, and known_limitations. Each context entry includes run_id, pull_id, mode, query, requested dates, encounter time, and run status. Formula-looking text is prefixed for spreadsheet safety. Downloads require an authenticated user with access to the project.

## Errors and security boundaries

401: missing/invalid session. 403: restricted admin endpoint. 404: resource inaccessible/missing where applicable. 409: incompatible pull state. 422: invalid input. Internal failures use generic 500 responses. Validation errors omit raw submitted inputs. Configured-source status never returns provider keys. Local users share organization-level access; fine-grained project grants and aggregate provider-account caps are roadmap work.

## Optional query suggestions

`POST /api/llm/generate-queries` uses local deterministic suggestions when OPENAI_API_KEY is absent. If that key is configured, this helper calls OpenAI and may incur separate charges; those charges are not covered by the social-provider pull ledger. It is not called automatically by the pilot collection UI.
