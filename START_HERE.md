# SocialScope research pilot

SocialScope supports topic/question -> optional dates -> source/query selection -> search preview -> bounded collection -> review/exclude -> descriptive analysis -> CSV export. It is an independent adaptation of SocialPulse, with a separate database, volumes, ports, and browser session key.

## Start locally

Install Docker Desktop (Linux containers/Compose) and Python 3 for the setup helper. Keep several GB free for dependency downloads, images, and builds. From this `socialscope` directory:

```powershell
python scripts/setup.py
```

Privately edit the newly created `.env`. Add the administrator's shared `SOCIALVAULT_API_KEY` and `XPOZ_API_KEY`; never commit or share this file. The pilot uses **the administrator's shared provider accounts**, not a separate paid account for each tester. Setup generates `SECRET_KEY` and `LOCAL_ADMIN_PASSWORD` and preserves any existing .env.

```powershell
docker compose up --build -d
docker compose ps --all
docker compose logs --tail 50 migrate seed
python scripts/check-connectivity.py
```

Open **http://localhost:3002**. Sign in with `LOCAL_ADMIN_EMAIL` and `LOCAL_ADMIN_PASSWORD` from your .env. Migrations and seed run automatically. The default email is `admin@socialscope.local`; setup generates the password. The API reference is http://localhost:8002/api/docs. Source availability and version/build appear on the dashboard. Missing keys permit browsing/setup but produce explicit unavailable collection outcomes.

Wait for `migrate` and `seed` to finish with exit code 0 before signing in; those one-shot containers are expected to exit. The connectivity helper checks HTTP reachability, not the full dependency-health response. Follow the health checks in [RUNBOOK](RUNBOOK.md).

Default host ports are frontend **3002**, backend **8002**, Redis **6381**, and PostgreSQL **5434**. Worker, scheduler, migration, and seed services have no published ports. See [Ports and configuration](docs/PORTS_AND_CONFIGURATION.md) for the full table and how to change ports. All localhost URLs in this guide assume the defaults.

If startup fails, use [RUNBOOK](RUNBOOK.md). Current environment validation and remaining checks are in [TESTING_GUIDE](TESTING_GUIDE.md); a clean Docker startup is still a required acceptance check wherever Docker cannot run.

## Handoff package

Share the application source, `docker-compose.yml`, Dockerfiles, `.env.example`, scripts, and documentation. Do not include `.env`, provider keys, login passwords, database backups, exports, validation artifacts, or `node_modules`. If sending an archive, exclude ignored files explicitly; Git ignore rules do not protect a manually zipped folder. The recipient should run setup to generate their own local login/signing secret, then obtain the shared provider credentials privately from the administrator.

The current `.gitignore` excludes `docs/`. For a Git-based handoff, include the intended documentation explicitly or provide it as a separate bundle. Keep that bundle under `docs/` beside these root guides so their links work.

This is a pilot handoff, not a production-readiness certification. The dated [validation record](TESTING_GUIDE.md) identifies the remaining Docker/PostgreSQL acceptance checks.

## First research workflow

1. Create a project with a question, description, and optional period. For example, public transit accessibility, local climate adaptation, or college costs.
2. Open Collections, select sources, and write a query. Dates are optional and preserve provider defaults when omitted.
3. Choose Search preview. Inspect examples, publication dates, source outcomes, and usage. It is a search preview, not a random or representative sample.
4. Revise the query if needed within the same pull. Unchanged completed previews are reused for 15 minutes. Use Continue this pull in history after a reload.
5. Set a total target of 100-5,000 and collect. Preview/revision/full runs together can accept no more than 5,000 unique posts for that pull. Provider limits may stop well below the target.
6. In Results, filter and follow original links. Exclude irrelevant posts reversibly; use Excluded scope to restore them. Analytics uses included posts.
7. Export included, excluded, or all observations. CSV includes provider, collection time, run/query/requested-period provenance, scope, and limitations.

## Allowances and important boundaries

X, Reddit, and YouTube are comparison sources. They have low allocation weights and **one combined 5-8-credit allowance, maximum eight**, across every preview, retry, query revision, and full collection in the pull. Eight with all three selected allocates 3/3/2 in X/Reddit/YouTube order. Unused shares do not automatically transfer. A full collection never refreshes the allowance. Start a new pull explicitly for a separate allowance; old/abandoned previews remain accounted for.

TikTok/Facebook have configurable SociaVault credit and attempt safeguards (defaults 20 each). Instagram retains Xpoz SDK-operation safeguards and the existing maximum of 300 results per search. **Instagram credit usage is not a hard bounded amount** because internal SDK operations/billing are not fully observable here. Unknown/timeout charges are retained rather than assumed free.

Each local installation enforces its own pull policy. Independent installs using the shared account do **not** enforce an aggregate account ceiling. Coordinate pilot use with the administrator. Selecting dates does not guarantee archive coverage, and a 5,000-post target does not promise 5,000 results. No live historical benchmark has been run. See the [evidence and benchmark proposal](docs/COLLECTION_FEASIBILITY.md).

No recruitment actions, candidate lists, health-specific background classification, automatic advanced AI analysis, or third-party telemetry are active in the pilot. Existing core provider behavior is retained. The public-hosting controls in the roadmap have not been implemented.

## Learn, operate, and give feedback

- [Learning handbook](docs/HANDBOOK.md): 14 sections covering actual architecture, code paths, ER/system diagrams, failure scenarios, exercises, and interview preparation.
- [Future improvement guide](docs/ROADMAP.md): feedback priorities, shared VM preparation, multiple-researcher controls, and justified scaling.
- [Collection feasibility and offline benchmark](docs/COLLECTION_FEASIBILITY.md): official evidence, code behavior, unknowns, and a no-spend planning/analyzer tool.
- [Runbook](RUNBOOK.md), [API reference](API.md), and [testing/validation](TESTING_GUIDE.md).
- [Feedback template](docs/FEEDBACK.md): include task, expected/actual behavior, version/build, and run ID. Remove credentials and sensitive research text.

After the first supervised pilot sessions, prioritize setup friction, query relevance, useful historical coverage, and interpretability of outcomes. Approve a separate bounded live benchmark before spending credits to investigate larger historical yields.
