# Historical collection feasibility and bounded benchmark

Evidence review: 2026-09-28. **No live provider requests or paid benchmarks were run.** Existing routing/date behavior remains in place; no automatic query expansion, comments, time-window splitting, or new historical pagination was added. The 5,000-post ceiling is a safeguard, not a yield guarantee.

## What is documented, inspected, and unverified

| Source | Official capability evidence | Inspected active code | Not established live |
|---|---|---|---|
| Instagram / Xpoz | Search supports date arguments; the introduction advertises a rolling historical window | `XpozAdapter._search_instagram` requests at most 300, reads SDK data, retains date compatibility fallback/local checks; no new paging | Older-period availability, relevance, unique yield, poll/retry billing, reproducible 300-result delivery |
| Instagram / SociaVault alternatives | General search finds accounts/hashtags/places; popular search returns topic posts with cursors; hashtag search returns hashtag posts | None is routed into SocialScope; current Instagram stays Xpoz | Whether alternative routes improve historical reach, rare-topic relevance, or cost-normalized yield |
| TikTok / SociaVault | Keyword route has cursor and coarse date/sort controls | Existing keyword paging and local date filtering retained; no automatic period slicing or query expansion | Historical depth, cursor stability, added unique in-range yield on later pages |
| Facebook / SociaVault | Group and profile post routes expose paginated posts | Google discovery followed by group/profile retrieval; discovery is budgeted; date-filtered behavior retained | Discovery recall, older-group coverage, benefit of researcher-supplied sources |
| X, Reddit, YouTube / SociaVault | Search endpoints and endpoint credit prices documented | Existing integrations retained behind one combined comparison allowance | Live account-specific charging, archive completeness, useful output under small shares |

Xpoz's [introduction](https://docs.xpoz.ai/introduction) describes a rolling 60-day historical window. Treat this as an advertised limitation, not evidence that sending an older start date yields a complete archive. The pinned SDK 0.7.5 wheel was inspected: search can launch an operation and poll status internally. The application sees outer SDK calls, not every internal request. This is why the Instagram request safeguard is **not** a hard credit ceiling.

Xpoz's [pricing](https://www.xpoz.ai/pricing/) lists 12 credits per Instagram query (and different query prices for other platforms). This is not per returned row. Do not compare one Xpoz credit with one SociaVault credit as if they were equal currency. SDK retry, polling, account-plan, and ambiguous-failure billing still require confirmation before a tightly bounded live Instagram benchmark. Runtime accounting leaves credits unknown rather than converting that headline price into an unjustified maximum.

SociaVault [Instagram search](https://docs.sociavault.com/api-reference/instagram/search) is an entity-discovery route, not a general post archive. [Popular search](https://docs.sociavault.com/api-reference/instagram/search-popular) and [hashtag posts](https://docs.sociavault.com/api-reference/instagram/search-hashtag) are candidates for a separately approved comparison. Popular search's documented request controls do not establish an exact historical interval. Do not replace the current adapter simply because another endpoint returns many posts.

The [TikTok keyword endpoint](https://docs.sociavault.com/api-reference/tiktok/search-keyword) exposes coarse `date_posted` periods such as yesterday, this week/month, recent months, and all time, plus sort/cursor controls. Exact research dates still require local filtering. Additional query variants could improve recall but also change scope and introduce overlap. Only researcher-approved variants should become separate recorded benchmark arms; count additional unique relevant observations, not gross rows.

For Facebook, [group posts](https://docs.sociavault.com/api-reference/facebook/group-posts) and [profile posts](https://docs.sociavault.com/api-reference/facebook/profile-posts) support source-oriented retrieval. The current adapter discovers candidate URLs using [Google search](https://docs.sociavault.com/api-reference/google/search), so poor discovery can limit output before post paging starts. Researcher-supplied groups/pages could reduce discovery waste and make the sampling frame explicit, but require a new input/provenance contract. That feature is proposed, not implemented.

## Endpoint cost policy

The active SociaVault allowlist uses the documented one-credit cost for each of these specific routes. It does not assume all vendor endpoints cost one credit.

| Adapter endpoint suffix | Reserved credits per attempt | Official reference |
|---|---:|---|
| `/twitter/search` | 1 | [X search](https://docs.sociavault.com/api-reference/twitter/search) |
| `/reddit/search` | 1 | [Reddit search](https://docs.sociavault.com/api-reference/reddit/search) |
| `/youtube/search` | 1 | [YouTube search](https://docs.sociavault.com/api-reference/youtube/search) |
| `/tiktok/search/keyword` | 1 | [TikTok keyword](https://docs.sociavault.com/api-reference/tiktok/search-keyword) |
| `/google/search` | 1 | [Google discovery](https://docs.sociavault.com/api-reference/google/search) |
| `/facebook/group/posts` | 1 | [Facebook group posts](https://docs.sociavault.com/api-reference/facebook/group-posts) |
| `/facebook/profile/posts` | 1 | [Facebook profile posts](https://docs.sociavault.com/api-reference/facebook/profile-posts) |

Unknown endpoints are blocked. Every controller attempt, including retries, reserves before network access. Timeouts are not automatically refunded. Reported `credits_used` is stored when present; otherwise successful calls are estimated. A reported charge above its reservation stops future requests for that pull. This cannot undo a vendor changing its cost without warning. Comparison routes remain SociaVault-only, with combined 5?8 credits (8 ceiling) and fixed platform shares. Instagram's outer operations remain explicitly unbounded in credits.

## Additional sources worth evaluating later

[TikTok Research Tools](https://developers.tiktok.com/products/research-api/) are an official research-oriented candidate for eligible researchers, subject to approval and applicable access conditions. Access is not assumed for this pilot. Meta Content Library is another research-access candidate, but its official page could not be retrieved during this review; no capability or eligibility conclusion is made here. Start by checking institutional eligibility and research-use conditions, then compare coverage and quotas. Existing researcher exports/imports may solve comparison needs more cheaply than another paid provider. No additional platform, provider, or comments collection has been implemented.

## Proposed benchmark: preparation only

`scripts/benchmark.py` has no network code and never launches a collection. Generate a reviewable plan:

```powershell
python scripts/benchmark.py plan --out benchmark-plan.json
```

The matrix has 12 baseline cells: broad topic **public transit**, niche topic **rural bus accessibility**; recent **2026-08-01 through 2026-08-31**, older **2024-08-01 through 2024-08-31**; Instagram, TikTok, Facebook. Dates are frozen for reproducibility. Revisit them deliberately if executing much later, and record the changed plan.

Each proposed cell starts at target 100 and at most two outer request attempts. SociaVault cells propose two credits, sufficient for a minimal Facebook discovery-plus-fetch path, with no guarantee of useful data. The Instagram cell records a 12-credit query estimate, **not an approved maximum**. Before live execution, the account owner must approve a total monetary cap and account-specific credit conversion for comparable per-cell spending, and establish a reliable provider-side Instagram bound. Until then all cells remain `approved: false`. No generated plan constitutes permission to spend.

Use a separate project/pull per baseline cell, identical language/region settings where supported, and no unrecorded query changes. Record query, dates, route/version, starting/ending provider balance when available, and UTC execution time. A revised-query or supplied-Facebook-source arm needs its own explicit scope and budget approval. Compare incremental unique yield to baseline instead of counting overlap twice.

Export **all** observations and save the authenticated jobs endpoint response to `runs.json`. Do not save Authorization headers or credentials. Analyze locally:

```powershell
python scripts/benchmark.py analyze --csv export.csv --runs runs.json --out report.json
python scripts/benchmark.py analyze --csv export.csv --runs runs.json --review review.csv --out reviewed-report.json
```

The optional review file has `id,relevant` columns; relevant values are yes/no/unsure. The report includes a deterministic subset of up to 30 in-period observations per run/source to review, unique in-period count, weekly/monthly distribution, missing publication dates, relevance among yes/no labels, available page metrics, stop reasons, and cumulative pull usage. Null relevance means unreviewed, not zero. The chosen subset is reproducible for practical inspection; it does not make provider search results a representative population sample.

Usage snapshots are cumulative per pull and must not be summed across preview/full runs. Save the final pull snapshot and provider-account reconciliation separately. Existing adapter page metrics provide later-page unique yield where available; missing SDK metrics remain unknown. If platform results were capped before storage, exported counts measure accepted observations, not all provider rows seen.

Decide from evidence: do later pages produce new in-period relevant posts at acceptable cost? Is the older period meaningfully represented? Does a niche query fail because of discovery, scope, dates, or indexing? If not, report the limitation and evaluate an approved alternative rather than increasing page limits to manufacture larger totals.
