# Decisions

# Week 1: the stack, the first call, and what it costs

---

## Week 1

**Run conditions.** Everything below was produced on:

- machine: AMD Ryzen 9 8940HX, RTX 5070 Laptop GPU, 32 GB RAM
- model: qwen3:4b-instruct (exactly as `ollama list` prints it)
- served by: Ollama, one request at a time, locally, OLLAMA_CONTEXT_LENGTH=8192
- date: 2026-09-22

Every number in this file is meaningless without those four lines, so they
are stated once here and referred to rather than repeated.

### 1. Machine and model set

I am now running the required model set plus both optional models:
`qwen3:4b-instruct`, `nomic-embed-text`, `qwen2.5:7b`, and `qwen3-vl:4b`
are all pulled, and `00_preflight.py` reports every line green.

That wasn't true during the live session — the wifi was slow, so I did the
lab (`qwen3:4b-instruct` and `nomic-embed-text` only) with `qwen2.5:7b`
still missing. Worth recording anyway: `project/models.py` lists
`qwen2.5:7b` as `REQUIRED` (needed for `00_preflight.py` to go fully green),
while the README's "before you arrive" list only asks for the other two
and calls `qwen2.5:7b` a homework pull "before week 9." That's a real
inconsistency in the course files. None of today's lab scripts actually
call `qwen2.5:7b` — 03_cost.py only uses the words "small"/"large" as price
*tiers*, not the model itself — so it cost nothing to defer during the
session and pull as homework afterward, which is what happened.

### 2. The first call

| | |
|---|---|
| finish reason | stop |
| prompt tokens | 24 |
| completion tokens | 45 |
| elapsed | 0.649 s |

One sentence on the finish reason: `stop` means the model ended the answer
on its own (it emitted its own end-of-turn token); if it had come back as
`length` instead, that would mean it hit `max_tokens=200` before it was
actually done, and my program would need to treat the text as a possibly
incomplete answer rather than a finished one — e.g. flag it, or retry with a
higher `max_tokens`, rather than trusting it as-is. I control the completion
token count indirectly (via `max_tokens` as a cap, and via prompt design);
the model decides how many it actually uses. Of the elapsed 0.649 s, a user
only feels the wall-clock time until the answer is fully visible — for a
non-streamed call like this one, that's the whole 0.649 s; with streaming
they'd feel mostly the time-to-first-token instead.

### 3. Variance

Homework: full live sweep, `02_variance.py --full`. The starter script's
`--full` flag didn't actually add the recording's other two prompts to the
live run (`LIVE_CELLS` only had two), so I extended `LIVE_CELLS`/`from_live`
with `open_short` and `open_reasoning`, matching the fixture's prompts, to
get a genuine eight-cell comparison.

| cell | distinct (recording, n=12) | distinct (mine, n=6) | median latency (mine) |
|---|---|---|---|
| closed_short, t=0.0 | 1/12 | 1/6 | 0.16 s |
| closed_short, t=1.0 | 1/12 | 1/6 | 0.16 s |
| open_list, t=0.0 | 1/12 | 1/6 | 0.56 s |
| open_list, t=1.0 | 11/12 | 6/6 | 0.65 s |
| open_short, t=0.0 | 1/12 | 1/6 | 0.59 s |
| open_short, t=1.0 | 5/12 | 5/6 | 0.58 s |
| open_reasoning, t=0.0 | 1/12 | 2/6 | 2.21 s |
| open_reasoning, t=1.0 | 12/12 | 6/6 | 2.03 s |

My machine agrees with the recording's pattern in every cell but one:
`open_reasoning` at t=0.0 came back 2/6 distinct, not fully identical. I
re-ran that exact cell by itself right after (6 fresh calls) and got 6/6
identical that time — so it is not a broken prompt or a code bug, it is
run-to-run non-determinism in the underlying hardware. `temperature=0.0`
makes the model's *token choice* deterministic (it always picks the
highest-probability token), but it does not guarantee bit-identical output
between separate runs on a real GPU: floating-point reduction order can
differ run to run, and small differences compound more over a long
978-character answer than a 3-character one. This is the checklist's own
warning in reverse — a result that *doesn't* match the recording is also
worth a second look, and here the second look shows the mismatch is real
and explainable, not a mistake.

Which cell still returns a single answer at temperature 1.0, and why that
one: `closed_short` ("What is the capital of Luxembourg? Answer in one
word."). It is not that "the temperature did not work" — it's that this
prompt's answer distribution is extremely peaked: there is essentially one
high-probability token ("Luxembourg") and no real competitor, so sampling
with temperature almost never lands on anything else. The other three
prompts ask for open-ended, multi-sentence answers with many equally
plausible wordings and orderings, so their distributions are much flatter
and temperature has something to actually sample across — `open_short` sits
in between (5/6 distinct) because a one-sentence answer has fewer places to
diverge than a multi-paragraph one.

Which cells a test asserting exact string equality would pass on, and what
that tells me about testing this system: it would reliably pass on
`closed_short` at either temperature. It would *usually* pass on the other
cells at t=0.0, but not with certainty — `open_reasoning` at t=0.0 just
showed me a run where it didn't, on a long enough answer. It would fail
outright, and unpredictably, on any open-ended cell at t=1.0. That tells me
exact-string equality is a reasonable test only for short, closed-form,
low-entropy outputs; for anything longer, even at t=0.0 it's a "usually,"
not a guarantee, and open-ended generation needs an evaluator that checks
meaning, not characters, which is what week 10 builds.

**The sentence that carries into week 10.** Repeatability depends on how
peaked the answer's probability distribution is, not on temperature alone,
and even a peaked/t=0.0 distribution isn't a hard determinism guarantee on
real hardware once the answer gets long enough for floating-point order to
matter: a closed, low-entropy prompt returns the same output even at temperature
1.0, while an open-ended, high-entropy prompt varies even in *how many*
genuinely distinct answers show up, so exact-string tests are only valid
for the former and the latter needs a semantic-equivalence evaluator
instead of string equality.

### 4. The cold start

- cold call: 2.10 s
- warm call: 0.18 s
- ratio: ~12x

What this implies for a system that uses more than one model, and what I
will do about it: my system will call two different models (`SMALL` and
`LARGE`), and a cold load costs roughly twelve times a warm call here — and
per `project/models.py`, on an 8 GB machine loading one model evicts the
other entirely, so the "cold start" isn't a one-time cost, it's a cost paid
every time you switch models. Consequence: I will not switch models inside
a single user-facing request. I'll route to one model per request/session
up front (e.g. classify-then-commit) rather than ping-ponging between
`SMALL` and `LARGE` mid-request, and where possible keep the model that
serves the latency-sensitive path warm.

### 5. Cost, estimated

A 200-case golden set, at the token cost of my long case (38 in, 200 out —
note: it hit the `max_tokens=200` cap, so this is a lower bound on what a
real, unbounded answer would cost):

| | one run | nightly for the semester (200 cases x 14 nights) |
|---|---|---|
| small tier | 0.00017 EUR | 0.47 EUR |
| large tier | 0.01246 EUR | 34.88 EUR |

Estimates against the price list dated 2026-08-10 (`project/prices.py`),
not measurements. Running locally, my actual monetary cost was zero.

Which tier I would run nightly, which I would run before a release, and why
not the same one for both: run the **small** tier nightly — at under 0.50
EUR for the whole semester it's cheap enough to run every night as a
regression check with no budget conversation needed. Reserve the **large**
tier for pre-release validation, run occasionally rather than nightly,
since paying ~35 EUR/semester to run the expensive model every single night
buys little over running it right before something ships.

### Deferred

Nothing left outstanding from the week 1 homework list. For the record,
what was deferred during the session and closed out afterward:

- `qwen2.5:7b` (`LARGE`) and `qwen3-vl:4b` (`VISION`), the two optional
  models, took about 45 minutes to pull on slow wifi. Both installed now;
  `00_preflight.py` is fully green.
- `02_variance.py`'s `--full` flag originally only produced 4 live rows (2
  prompts x 2 temperatures) instead of 8, because `LIVE_CELLS` only defined
  `closed_short` and `open_list`. Fixed for the homework: added
  `FULL_EXTRA_CELLS` with the recording's other two prompts (`open_short`,
  `open_reasoning`) and made `from_live()` include them when `--full` is
  passed. The 8-cell table above is from the fixed script.
- Read `project_spine/README.md` and skimmed `project/contracts.py`, as the
  homework asks. Takeaways worth keeping: (1) every `Trace` requires
  `Conditions` (model, temperature, date) by the type system, not by
  convention — you cannot write a run without saying what produced it; (2)
  week-specific data goes in the untyped `notes`/`settings` dicts rather
  than widening the core schema, so the core fields never change under
  later weeks; (3) `schema_version` is on every artifact so a stale file
  fails loudly in `project.verify` instead of silently in week 10.

---

# Week 2: a structured-output extractor, measured

## Week 2

**Run conditions.** model: qwen3:4b-instruct | temperature: 0.0 | prompt
version: week02-zero-shot-v1 | served locally | date: 2026-09-22 | scored
on: the recording (`--replay`, to develop the scorer) and my own machine
(live, for the numbers below).

### 1. The output contract

The conventions I chose, and why:

- due_date, when the message states no date: `null`. The schema types
  `due_date` as `date | None`, so "no date" is a real absence, not the
  string `"null"` or an empty string — those aren't representable at all,
  which removes a whole category of scorer edge case rather than handling
  it.
- due_date, when the message states only a relative expression (e.g.
  "before the end of the month", "as soon as possible"): also `null`.
  Only an actual calendar date counts as a date; a relative expression is
  not something the model should resolve to a specific day on its own
  (it has no way to know what day "today" is with confidence, and
  guessing one is worse than admitting there isn't one).
- quote, and what "verbatim" means in my scorer: exact Python `in`
  substring search against the raw document text, no lowercasing, no
  stripping, no whitespace normalization. The moment that check is
  relaxed, the field stops measuring whether the model copied and starts
  measuring whether it approximately copied — and copying exactly is the
  entire point of a field that's free to check.
- what my scorer does with a record that failed schema validation: counts
  it in `invalid`, and counts **every field as wrong** for that document,
  not skipped.

A scorer that silently skips records it couldn't parse would report a
number that *improves* as the model gets worse (fewer parseable records
means a smaller, easier denominator) — the most dangerous kind of metric,
because it looks like progress while hiding failures.

### 2. Zero-shot, per field

| field | correct | of |
|---|---|---|
| category | 8 | 10 |
| urgency | 9 | 10 |
| due_date | 8 | 10 |
| quote | 9 | 10 |
| invalid records | 0 | 10 |

Tokens: 4,158 prompt + 546 completion over the 10 calls (415.8 / 54.6 per
call on average). Estimated cost on the small tier: **1.27 EUR per
thousand calls**, against the price list dated 2026-08-10. Estimate, not
a measurement — running locally, the actual cost was zero.

My prediction, written before block 3: examples will help most on
**due_date** and **category**, because the failures I'm seeing are exactly
the kind examples fix — REQ-01/REQ-10 hallucinate a date on messages with
no calendar date at all (the null convention isn't being followed), and
REQ-04/REQ-08 confuse the facilities/hardware/access boundary in both
directions. I expect **quote** to move least, since it's a mechanical
copy task the model is already close to getting right (9/10), and I
expect it could even get *worse* if my examples show tidied quotes
(checked for that explicitly when building the block).

### 3. Few-shot

Examples chosen, and the job each one does:

| example | why it is in the block | field it should move |
|---|---|---|
| EX-01 (en) — badge reader, access/standard/null | a badge reader is physically hardware, but the correct label is "access" — this is the exact boundary REQ-08 got wrong (in the opposite direction) | category |
| EX-02 (fr) — elevator stuck, facilities/urgent/null | an elevator is a facility, not "hardware" — the same boundary REQ-04 got wrong, from the other side; also non-English | category |
| EX-03 (de) — laptop charger, hardware/standard/2026-09-20 | hardware *with* a real due date, so the block shows the "a date is present" convention too, not only the null one; also non-English | due_date, category |
| EX-06 (en) — window leak, facilities/urgent/null | facilities again, but a non-device object (a window), reinforcing the boundary from yet another angle | category |

| field | zero-shot | few-shot | move |
|---|---|---|---|
| category | 8/10 | 8/10 | +0 |
| urgency | 9/10 | 9/10 | +0 |
| due_date | 8/10 | 8/10 | +0 |
| quote | 9/10 | 10/10 | +1 |

### 4. What got worse

Nothing got worse **as a count** — no field's hit rate dropped. But I
checked the failure lines, not just the counts, and one thing changed
shape without improving: REQ-04's category error was `hardware` (wrong)
under zero-shot and became `access` (also wrong) under few-shot. Despite
including two examples specifically meant to teach the
facilities/hardware/access boundary (EX-01: hardware-looking object →
access; EX-02/EX-06: facilities, not hardware), the model just moved to a
*different* wrong answer rather than the right one — my prediction from
section 2 was wrong about category moving. REQ-08's category error
(`access`, expected `hardware`) didn't move at all.

The due_date hallucinations also didn't disappear (REQ-01, REQ-10 both
still wrong), and the specific wrong dates changed between the zero-shot
and few-shot runs (`2023-10-10`→`2023-09-07`, `2023-12-31`→`2024-12-31`) —
that looks like generation noise rather than anything the examples
touched, since 3 of my 4 examples explicitly demonstrate the null
convention and it still didn't take.

What genuinely disappeared: REQ-04's quote error (the zero-shot run
produced a garbled, non-verbatim quote containing a stray non-Latin
character mid-word; few-shot's quote was clean and verbatim). That's a
real fix, not a reshuffle — it's the only field where both the error
count and the underlying failure actually went away.

### 5. What the examples cost

- extra input tokens per call: 276
- per thousand calls: 276,000
- estimated euros per thousand calls on the small tier: 0.06 EUR (the
  example block alone, small-tier input-token price only), against the
  price list dated 2026-08-10. Estimate, not a measurement.

### 6. Ship it or not

**Not on this evidence.** The only field that actually improved was
`quote` (+1 out of 10), for a ~57% increase in total tokens over the
10-document run (4,704 → 7,368, prompt cost alone up 276 tokens/call).
Category,
urgency, and due_date — the fields I predicted would move — didn't, and
one category error just changed which wrong answer it gave. Ten records
is too small a sample to call a single-document improvement a real
effect, and I'd rather say that than claim a win.

What would change my mind: the same comparison on a larger set (week 10's
harness) showing the quote-fidelity gain holds up over more than one
document, and ideally isolating *why* zero-shot's quote failed — if it's
a generation-length/decoding artifact rather than something examples fix,
it might be cheaper to fix with a higher `max_tokens` or a stricter
`max_length` on the field than to pay 276 tokens on every call forever.
If I had to keep exactly one example, it would be **EX-02** (the facility
example that most directly targets the still-unresolved facilities
confusion), on the chance that a single, less diluted example does what
four examples spread across multiple goals didn't.

### Sensitivity variant

Variant assigned: none — I'm doing this asynchronously, not in a group,
so I picked **role**, the least ambiguous variant to test cleanly. What I
changed: prepended exactly one line, `"You are a senior service desk
analyst."`, to the few-shot prompt from block 3, nothing else.

What moved: **nothing**. Every field, both live runs: category 8/10,
urgency 9/10, due_date 8/10, quote 10/10 — identical counts, and the
per-language breakdown (en/fr/de) also showed identical error counts in
each language. This matches the brief's own prediction: on a task with
closed label sets and a schema doing the structural work, a persona buys
nothing and costs tokens (total tokens rose from 7,389 to 7,485 over the
10-document run — about 10 tokens/call just for that one prepended
sentence) on every call. A knob that moves nothing measurable is still a
real result — it tells me persona framing isn't worth arguing about for
this kind of task, so if I'm optimizing this prompt later, that's not
where to spend effort.

### The gold set

Ten cases written to `artifacts/goldset.json`, tagged by language
(`lang:en`/`lang:fr`/`lang:de`) and by category, confirmed valid by
`python -m project.verify`.

One thing my scorer cannot currently detect: a **correctly formatted but
wrong date**. My due_date check only compares the ISO string against the
gold string for exact equality, so `"2026-09-16"` scores identically
wrong whether it's off by one day or off by a year — the scorer can tell
me *that* a date is wrong but not *how* wrong, and a near-miss date (which
might indicate the model read the right sentence but miscounted) looks
exactly like a wholly invented one in the aggregate counts. I'd need to
keep the actual gold and predicted values in the failure log (which I do)
and read them by hand to tell those apart — the Scoreboard's per-field
counts alone cannot.

### Deferred

Nothing left outstanding from the week 2 TODO list (1–8 all done,
`project.verify` passes with `goldset.json` valid). Not done, and not
recoverable after the fact: the two live checkpoints — same situation as
week 1, noted there.
