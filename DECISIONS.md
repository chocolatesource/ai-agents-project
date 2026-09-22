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

I am running the required model set, minus one: `qwen3:4b-instruct` and
`nomic-embed-text` are pulled, but `qwen2.5:7b` is not, because the wifi
here was slow today and it's a 4.7 GB pull.

This matters more than it looks: `project/models.py` lists `qwen2.5:7b` as
`REQUIRED` (needed for `00_preflight.py` to go fully green), but the
README's "before you arrive" list only asks for the other two, and calls
`qwen2.5:7b` a homework pull "before week 9." That's an inconsistency in the
course files, not something I misread — I'm treating the README as
authoritative for week 1 and will pull `qwen2.5:7b` before week 9 as it
instructs. Until then, `00_preflight.py` reports one FAIL line
("model server and required models: Missing qwen2.5:7b"), which is the
known-and-understood red line checklist item 1 allows for. None of today's
scripts actually call `qwen2.5:7b` — 03_cost.py only uses the words
"small"/"large" as price *tiers*, not the model itself.

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

| cell | distinct (recording, n=12) | distinct (mine, n=6) | median latency (mine) |
|---|---|---|---|
| closed_short, t=0.0 | 1/12 | 1/6 | 0.18 s |
| closed_short, t=1.0 | 1/12 | 1/6 | 0.18 s |
| open_list, t=0.0 | 1/12 | 1/6 | 0.62 s |
| open_list, t=1.0 | 11/12 | 6/6 | 0.61 s |

My machine agrees with the recording in every cell: both stay at a single
distinct answer at t=0.0, `closed_short` stays at a single answer even at
t=1.0, and `open_list` scatters into (almost) all-distinct answers at
t=1.0.

Which cell still returns a single answer at temperature 1.0, and why that
one: `closed_short` ("What is the capital of Luxembourg? Answer in one
word."). It is not that "the temperature did not work" — it's that this
prompt's answer distribution is extremely peaked: there is essentially one
high-probability token ("Luxembourg") and no real competitor, so sampling
with temperature almost never lands on anything else. `open_list` asks for
an open-ended, multi-sentence answer with many equally plausible wordings
and orderings, so its distribution is much flatter and temperature has
something to actually sample across.

Which cells a test asserting exact string equality would pass on, and what
that tells me about testing this system: it would reliably pass on
`closed_short` at either temperature, and on any cell run at t=0.0. It would
fail, unpredictably, on `open_list` at t=1.0 (and presumably on other
open-ended cells at t=1.0, per the recording's `open_short`/
`open_reasoning` rows). That tells me exact-string equality is only a valid
test strategy for closed-form, low-entropy outputs or deterministic
(t=0) runs — open-ended generation needs an evaluator that checks meaning,
not characters, which is what week 10 builds.

**The sentence that carries into week 10.** Repeatability depends on how
peaked the answer's probability distribution is, not on temperature alone:
a closed, low-entropy prompt returns the same output even at temperature
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

- `qwen2.5:7b` (`LARGE`) not pulled today — slow wifi, 4.7 GB, and nothing
  in today's TODOs actually calls it. Will pull before week 9 per the
  README's homework instruction; `00_preflight.py` will show one known FAIL
  line until then.
- Homework: `02_variance.py --full` currently only produces 4 live rows (2
  prompts x 2 temperatures), not the 8 the recording has, because
  `LIVE_CELLS` only defines `closed_short` and `open_list` — the `--full`
  flag is accepted by `from_live()` but not actually used to add the other
  two prompts (`open_short`, `open_reasoning`). Worth revisiting as an
  "if I finish early" extension, not done today.
