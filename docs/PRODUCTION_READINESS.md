# Production review — November 17, 2026

This record separates application changes verified locally from deployment checks on the actual VM. It does not certify a running installation. Use the [production runbook](../RUNBOOK.md#production-deployment-controls---2026-11-17) for deployment.

## Changes made

- Replaced the login's Pilot access label with Account access and aligned API/source metadata on one shared application version. Local builds identify themselves as development; the production release example no longer uses a pilot tag. Historical changelog/test records and existing database records are preserved.
- Renamed active administration components/schemas to describe their current purpose. Renamed the deterministic, no-key query generator to LocalQueryAdapter: it suggests queries locally and does not synthesize collected posts. Real provider adapters still return no data without credentials; test-only synthetic adapters are not selected by those runtime adapters. Missing provider provenance is recorded as unknown rather than mock.
- Added explicit production settings checks for a non-placeholder signing secret of at least 32 characters and exact HTTPS browser origins. Development remains separate. Configuration-validation errors suppress input values in traceback text.
- Made dependency readiness return HTTP 503 when PostgreSQL/Redis fails or times out. Healthy responses remain HTTP 200. Probes are bounded/concurrent, database failures roll back, and Redis connections close on success/failure.
- Updated Next.js 14 to 16.4.6, React/React DOM to 19.3.1, React types to 19.3.0, and Recharts to compatible 2.15.4. Both frontend Dockerfiles use Node 22. Webpack is selected explicitly, standalone output is always enabled, and arbitrary remote image optimization is disabled because the application does not use next/image. The [Next.js support policy](https://nextjs.org/support-policy) lists 14 as unsupported; the [upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-16) covers React, Node, and bundler requirements.
- Replaced python-jose with PyJWT 2.15.1 and require subject/expiration claims while retaining HS256 compatibility. Updated FastAPI, MCP, and python-multipart pins in response to dependency findings. Testing dependencies live in a separate development requirements file; tests are excluded from the backend image context.
- Corrected a stale analytics test: an inaccessible/missing project must return 404, rather than a successful empty dataset. Authorization behavior was preserved. Tests and real limitations were not removed to make the release look ready.

## Dependency audit scope

The network-enabled npm production audit after upgrades reported zero known runtime vulnerabilities. The full npm audit still reports ten high-severity development-tool findings through picomatch and Tailwind 3's file-scanning dependency chain. These tools run during builds/development and are not copied into the standalone runtime. Their inputs are repository paths/patterns, not a public application endpoint. Do not interpret the production-only result as a clean audit of every tool; a Tailwind major upgrade remains separate work.

The resolved Python validation folder (runtime plus development requirements, on Windows/Python 3.12) reported no known vulnerabilities after updating MCP to 1.30.0. The Linux images still need their own build/scan because platform-specific dependencies can differ. Python validation and final build results are recorded in [TESTING_GUIDE.md](../TESTING_GUIDE.md). Advisory databases and transitive dependencies change; repeat network-enabled audits for future releases. A zero-known-finding audit is not a security guarantee.

## Checks still required on the VM

Local validation completed: **249 backend tests passed, one PostgreSQL-only check skipped**, all six frontend test scripts passed, TypeScript and the production standalone build passed, and both Compose templates parsed. The built login/JavaScript assets and password/error behavior were smoke-tested. Full evidence and platform limits are in the [validation record](../TESTING_GUIDE.md).

1. Supply private production settings and create/verify isolated empty volumes and the restricted database login.
2. Build the Linux images, apply migrations, provision the administrator, and verify every service's health/resource limits.
3. Configure DNS, Nginx, Certbot, HTTPS, and renewal; verify the actual public origin and internal-only service ports.
4. Exercise authentication, private projects with two users, worker delivery, exports, account controls, feedback, and activity cleanup on PostgreSQL. Local SQLite tests do not prove PostgreSQL concurrency/ownership behavior.
5. Verify capacity beside SocialPulse/LitIQ, reboot/restart behavior, monitoring, and backup restoration. No paid provider benchmark or hosted capacity test was performed by this review.
