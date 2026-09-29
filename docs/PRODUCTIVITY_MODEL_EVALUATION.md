# Productivity Assistant: local model evaluation

First measured results for the [plan's](PRODUCTIVITY_IMPLEMENTATION_PLAN.md) M5
decision ("which local model"), run ahead of M4 so the capture design is based on
evidence. **All numbers below are measured results** from one run on synthetic
data. They are not targets.

## Setup (run 2026-09-29)

| Item | Value |
| --- | --- |
| Hardware | Mac17,5, Apple A18 Pro, 8 GB, macOS 27.0 |
| Runtime | Ollama 0.34.0, already running; nothing downloaded or reconfigured |
| Harness | [evals/capture/run.py](../evals/capture/run.py), prompt `capture-v1`, JSON-schema output, `think: false` |
| Options | temperature 0, seed 42, context 2,048, output cap 256, timeout 60 s, one request at a time |
| Cases | [30 synthetic notes](../evals/capture/cases.json): 15 explicit, 8 ambiguous, 7 adversarial (injected instructions, unknown projects, invalid dates) |
| Scoring | Code validation first (invalid dates, unknown projects, out-of-range values dropped, never repaired), then every field compared to the accepted gold values |
| Raw data | [evals/results/](../evals/results/) |

Models (full digests):

| Model | Size / quantization | Digest |
| --- | --- | --- |
| granite4:350m-h | 340M, Q8_0 | `7145075ed3d6da48bd41cafd8bed8171936abe0ece819aa1e516fd98881aa6a4` |
| qwen3:0.6b | 752M, Q4_K_M | `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435` |
| qwen3.5:2b | 2.3B, Q8_0 | `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df` |
| llama3.2:latest | 3.2B, Q4_K_M | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` |
| hermes3:3b | 3.2B, Q4_K_M | `a8851c5041d400c8eece484771e0a9f438e6500de9f22150ef2863bf7209fbd9` |

`dolphin3:8b` was not run: at 4.9 GB it would leave too little memory for the app
and the OS on an 8 GB Mac.

## Results

Correct-field counts are out of 30. "Whole draft" means every field is correct.

| Model | Whole draft | Title | Due date | Project | Effort | Importance | Warm p50 / p95 | Cold | Resident memory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| granite4:350m-h | 1 | 26 | 14 | 23 | 27 | 3 | 1.1 / 1.2 s | 7.2 s | 0.41 GB |
| qwen3:0.6b | 4 | **29** | 15 | 28 | 25 | 6 | **0.8 / 1.0 s** | 2.9 s | 0.68 GB |
| qwen3.5:2b | 5 | 26 | 22 | 25 | **29** | 8 | 4.3 / 4.8 s | 12.1 s | 2.32 GB |
| **llama3.2:latest** | **8** | 25 | **23** | **29** | **29** | **12** | 3.2 / 3.6 s | 9.4 s | 2.21 GB |
| hermes3:3b | 1 | 28 | 14 | 23 | 19 | 11 | 3.1 / 3.5 s | 9.0 s | 2.21 GB |

- Every model returned schema-valid JSON for all 30 cases. There were no timeouts
  and no truncated replies. The largest prompt was 211 tokens, well inside the
  1,000-token capture budget.
- Code validation rejected 2 to 13 invalid fields per model, such as an unknown
  project or an impossible date. None of those values reached a draft.
- None of the models could be trusted to fill a whole draft. The best one,
  llama3.2, got 8 of 30 drafts fully correct.

## What went wrong

These patterns come from llama3.2, the best model.

- **Importance:** it answered 3 ("high") for 23 of 30 notes, although most notes
  say nothing about importance.
- **Weekday dates:** it resolved "Friday", "Thursday" and "Saturday" to the wrong
  day, and turned vague phrases ("next week", "think about") into dates.
- **Titles:** it sometimes cut titles down to one or two words ("Renew", "Mow").
- **Handled well:** it matched projects correctly (29/30), never invented a
  project that wasn't on the list, and read explicit durations correctly (29/30).

## Recommendation for M4

1. **Code resolves dates and importance.** A deterministic parser in the app
   handles weekdays, relative days and explicit dates. Keyword rules set
   importance ("urgent", "low priority"). The model only reports the date phrase
   it found. This follows the design principle that code owns calculations.
2. **The model proposes the title, project and effort,** its strongest fields.
   Code validates them, and you still confirm every draft.
3. **Model: qwen3:0.6b** (digest above), **decided 2026-09-29**. When code
   handles dates and importance, qwen3:0.6b almost ties llama3.2 on the fields
   the model still fills (82 vs 83 of 90 for title, project and effort). It is
   about four times faster (0.8 s vs 3.2 s typical warm reply) and uses about a
   third of the memory (0.68 vs 2.21 GB), which suits an 8 GB Mac. llama3.2
   remains the fallback if the held-out re-test shows qwen3:0.6b falling short.
4. **Re-run on a new held-out set** after the prompt changes for step 1. These 30
   cases have now been looked at, so they count as development data.

The model choice is decided. M4 itself still needs a separate go-ahead.

## Re-running

```sh
.venv/bin/python evals/capture/run.py llama3.2:latest qwen3:0.6b
```

The Ollama service must already be running. The script never pulls models, and
it writes a timestamped file to `evals/results/`.
