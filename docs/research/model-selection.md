# OpenAI model selection for delegation

Draft reference · checked 2026-09-10 (Asia/Bangkok).
Scope: OpenAI models listed by this repository's Pi environment, not all OpenAI models.
This is decision support, not a model allowlist, launch authorization, or automatic routing policy.
Refresh prices and access before consequential selection. Actual task results outrank a generic ranking.

## Core dimensions

| Capability | What to evaluate | Useful evidence |
| --- | --- | --- |
| Reasoning and planning | Ambiguity, dependencies, tradeoffs, unfamiliar problems | Comparable reasoning benchmarks and realistic planning tasks |
| Coding and debugging | Correct changes, diagnosis, tests and review | Coding-agent benchmarks with harness disclosed; repository acceptance tests |
| Tool use and execution | Correct tools, safe actions, end-to-end completion | Agentic evaluations and actual tool outcomes |
| Instruction and coordination reliability | Scope, contracts, questions, handoffs and acceptance | Fresh local scenarios with observable boundary checks |
| Context and evidence judgment | Constraint retention, grounded claims, uncertainty | Long-context and knowledge-reliability evaluations; source-checking tasks |

Keep efficiency separate: total cost, elapsed time, tokens and subscription usage per
acceptable result, including handoffs, review, retries and repair. Do not average these
capabilities into an invented intelligence score. Add specialized dimensions only for a
specific task. Evidence labels below: **vendor**, **external benchmark**, **local smoke**,
and **unknown**. A benchmark is evidence about its tasks/configuration, not all five dimensions.

## Available versus listed

`pi --list-models openai` listed these eight IDs under `openai-codex` on the checked date:

- `gpt-5.3-codex-spark`
- `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5`
- `gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6-sol`, `gpt-6-astra`

Listing is catalog evidence, not a successful request or permission to launch. In this
research/evaluation context, Luna medium/high subject identities were verified; the
coordinator environment reports Astra, but its current effort was not independently exposed.
Other models were not launched as availability probes.

OpenAI says GPT-5.4 and GPT-5.4-mini retired from Codex with ChatGPT sign-in on
2026-08-31; API-key access is not affected [1]. Treat these two local entries as requiring
access verification, not delegation defaults. Spark is a text-only Pro research preview
with separate usage limits and no API availability at launch [1,2]. Do not infer current
account entitlement from its presence in Pi.

Pi reports 272K context / 128K max output for the listed models except Spark (128K/128K).
These are client-advertised limits, not the same as the larger context limits on some API
model pages. Do not budget a Pi session using API context capacity without checking the client.

## Price and usage snapshot

Standard short-context USD per million tokens, not subscription charges [3]:

| Model | Input | Cached input | Cache write | Output |
| --- | ---: | ---: | ---: | ---: |
| Luna | $0.20 | $0.02 | $0.25 | $1.20 |
| Terra | $2.00 | $0.20 | $2.50 | $12.00 |
| Sol | $4.00 | $0.40 | $5.00 | $20.00 |
| Astra | $10.00 | $1.00 | $12.50 | $50.00 |

Sol's listed promotional price is available at least through 2026-11-21. Long-context
rates differ: the price page lists 2x input/cache rates and 1.5x output for these four
models. Verify applicable thresholds, service tier, region and tools before costing a job.

Older-model pages show input / cached input / output per million as GPT-5.5
$5 / $0.50 / $30, GPT-5.4 $2.50 / $0.25 / $15, and GPT-5.4-mini
$0.75 / $0.075 / $4.50 [4–6]. The readable extraction includes a nearby
“Batch API price” label: standard-versus-Batch classification requires verification
before using these figures for costing. These pages do not establish ChatGPT-sign-in
access. No comparable Spark API rate is established here.

Codex's published standard credit rates per million tokens [2]:

| Model | Input credits | Cached input credits | Output credits |
| --- | ---: | ---: | ---: |
| Luna | 5 | 0.5 | 30 |
| Terra | 50 | 5 | 300 |
| Sol | 100 | 10 | 500 |
| Astra | 250 | 25 | 1,250 |
| GPT-5.5 | 125 | 12.5 | 750 |
| GPT-5.4 | 62.5 | 6.25 | 375 |
| GPT-5.4-mini | 18.75 | 1.875 | 113 |
| Spark | Separate preview limit | — | — |

Included usage, purchased credits and API dollars are different accounting surfaces.
Do not convert estimated API cost into the user's actual subscription bill. Model,
reasoning, tool activity, context and cache behavior affect usage. Provider token totals
can include repeated/cached input; do not add separately reported reasoning tokens again
when already included in output. Use actual meter definitions and non-overlapping token
categories when calculating costs. No account identifiers or live quota snapshots are stored here.

## Capability evidence and candidate assignments

The following are **vendor descriptions and selection hypotheses**, not local comparative
performance results [1]. Each non-Luna model's local five-dimension performance is unknown.

| Model | Vendor positioning | Candidate assignment to validate locally |
| --- | --- | --- |
| Luna | Clear, repeatable, high-volume work; focused coding | Bounded edits, extraction, checks with explicit acceptance criteria |
| Terra | Everyday reasoning and tool use; production work | Broader implementation or integration needing judgment |
| Sol | Complex, ambiguous, high-value coding and research | Difficult diagnosis, architecture alternatives, substantive review |
| Astra | Hard end-to-end tasks with sustained judgment | Complex coordination, cross-tool work and evidence synthesis |
| GPT-5.5 | Previous-generation complex professional/coding model | Existing known-good assignments; compare before replacing |
| GPT-5.4 | Professional coding/reasoning | API-access legacy use; verify access before any proposal |
| GPT-5.4-mini | Responsive coding and subagents | API-access bounded work; verify access first |
| Spark | Near-instant text-only coding iteration | Latency-sensitive bounded iteration, if preview access is confirmed |

No model is inherently a manager or worker. Match the assignment to evidence, authority
and budget. A stronger model may reduce total cost through fewer failed attempts; a higher
per-token price alone does not settle that comparison. Terra's vendor positioning is not
proof that it beats Luna plus review, or Sol at lower effort.

## External intelligence and coding scores

Use scores only with their benchmark snapshot, model effort and harness. They are not IQ,
success probabilities, or instruction-compliance scores. Current AA model pages identify
Intelligence Index v4.3, but their extracted chart text did not expose all numeric values.
Do not fill missing scores by inference or combine old and new snapshots.

**Same-article comparison: Artificial Analysis Astra evaluation [7]**

| Configuration | Intelligence Index | Coding Agent Index (Codex) |
| --- | ---: | ---: |
| Astra max | 53 | 62 |
| Sol max | 47 | 55 |
| Terra | Unknown in this snapshot | Unknown in this snapshot |
| Luna | Unknown in this snapshot | Unknown in this snapshot |

The article reports Astra +6 Intelligence points over Sol and names their Coding Agent
scores. It reports mixed subtask outcomes: Astra leads Terminal-Bench v4.0 (56% versus
37%) and SWE-Atlas-QnA (62% versus 54%), but trails Sol on DeepSWE (68% versus 72%).
That is a reason to retain task-specific evidence rather than assume universal superiority.
The article also reports stronger knowledge-work analytical results but weaker presentation
quality than Sol; it does not establish our coordination or question-following reliability.

**Historical GPT-5.6 launch comparison, separate snapshot [8]**

| Configuration | Intelligence Index (article's v4.1 snapshot) | Coding Agent Index (Codex; historical) |
| --- | ---: | ---: |
| Sol max | 59 | 80 |
| Terra max | 55 | 77 |
| Luna max | 51 | 75 |

Do not compare these historical values with Astra's later 53/62. The older article's prices
also differ from today's official prices. Its intelligence/cost frontier findings apply to
that evaluation and pricing snapshot, not today's subscription usage or every assignment.
Comparable current scores for GPT-5.5, GPT-5.4, mini and Spark are not established here.

AA evaluates a specified harness; Codex benchmark results are not Pi results. The
GPT-5.6 Luna API page lists `max` [9], but no equivalence to a Pi effort setting was verified.
Never label our medium/high runs with max benchmark scores. Higher effort can improve
hard tasks but also consumes time/tokens; it is not a guaranteed compliance repair [1].

## Local instruction and coordination evidence

Four fresh Luna design-only sessions used identical scenario prompts across medium/high,
installed team-design guidance, and an all-criteria presentation rubric. All successfully
loaded team-design and produced hierarchy/work diagrams without launches or file edits.

| Scenario | Medium | High |
| --- | --- | --- |
| Initial team | Fail: coordinator details and explicit question omitted | Same omissions |
| Existing-team redesign | Fail: explicit question omitted | Pass on frozen gates, with caveats |
| Aggregate reported tokens | 53,178 | 76,443 |

High used about44% more reported tokens across the pair, including cached/repeated input.
Different cache behavior and skill reads prevent calling this a pure thinking-effort cost.
One run per condition/scenario is smoke evidence, not a model intelligence ranking.
Redesign runs also made unnecessary parent-directory discovery; the high response's final
choices were not numbered. Preserve those caveats rather than hide them behind the pass.

These tests preceded the coordinator-coverage clarification in commit `13bff55`; that
clarification has static tests, not a fresh behavioral retest. Earlier waiting tests also
showed that Luna medium could yield and recover through a coordinator watchdog after a
narrow instruction correction; one success does not establish general reliability.

Private local provenance, when present (not required or portable):
`.agents/var/skills/automata-agent-evaluation/team-diagrams/`,
`team-diagrams-high/` and `coordination-finish/` under the same evaluation owner.
Normal agent histories are not embedded in this reference.

## How to use this reference

Start from the assignment's dominant capability and acceptance criteria. Choose a candidate
within approved models/effort and verify runtime support. For clear bounded tasks, test a
lower-cost candidate; for costly failure, ambiguity or integration risk, consider stronger
reasoning or independent review. Compare total acceptable-result cost rather than token
price alone. Do not escalate effort automatically after a failure: first distinguish
missing context, instruction ambiguity, activation, execution and capability problems.

A meaningful future comparison should hold task, acceptance gates and harness steady,
record effort and cache accounting, and report uncertainty. Keep unknowns visible. No
benchmark runs, global model defaults, or team-launch authority are created by this document.

## Sources

All checked 2026-09-10; dynamic pages may change. Official claims and external evaluations
are intentionally separated. AA reports pre-release evaluation cooperation with OpenAI
in its GPT-5.6 article; it is external evaluation, not our own replication.

1. [OpenAI Codex models and reasoning guidance](https://developers.openai.com/codex/models)
2. [OpenAI Codex pricing, credits and access](https://developers.openai.com/codex/pricing/)
3. [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
4. [GPT-5.5 API model](https://developers.openai.com/api/docs/models/gpt-5.5)
5. [GPT-5.4 API model](https://developers.openai.com/api/docs/models/gpt-5.4)
6. [GPT-5.4-mini API model](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
7. [Artificial Analysis: benchmarking GPT-6 Astra](https://artificialanalysis.ai/articles/benchmarking-gpt-6-astra)
8. [Artificial Analysis: GPT-5.6 launch evaluation](https://artificialanalysis.ai/articles/gpt-5-6-has-landed)
9. [GPT-5.6 Luna API model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
10. [AA intelligence methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking)
11. [AA Luna model page](https://artificialanalysis.ai/models/gpt-5-6-luna)
