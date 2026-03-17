# HA Voice LLM Benchmark Results — March 2026

Benchmark of 7 local LLMs for Home Assistant voice intent processing on consumer GPU hardware, testing 4 system prompt configurations across 2 inventory tiers.

## Top-Line Results

**Overall accuracy (averaged across small + medium tiers, 3 runs each):**

| Model | Quant | Default | Always Name | + /no_think | + Sensor hint | Avg Latency |
|-------|-------|--------:|------------:|------------:|--------------:|------------:|
| **Qwen3 8B** | Q4_K_M | 45.4%\* | 65.5% | **74.8%** | 72.8% | 1.9s / 37.6s\*\* |
| **Qwen2.5 7B** | Q5_K_M | 63.4% | 70.3% | 72.5% | 71.4% | 2.3s |
| Qwen2.5 7B | Q4_K_M | 56.9% | 66.3% | 65.8% | 67.0% | 2.1s |
| Functionary-sm 3.1 | Q5_K_M | 53.3% | 61.4% | 61.4% | 57.8% | 1.3s |
| Functionary-sm 3.1 | Q4_K_M | 47.8% | 59.2% | 58.2% | 57.8% | 1.2s |
| Meta-Llama 3.1 8B | Q4_K_M | 30.3% | 54.2% | 48.2% | 43.7% | 1.5s |
| Llama 3.2 3B | F16 | 12.3% | 21.4% | 19.2% | 20.1% | 1.8s |

\* n=1 for small tier (see Qwen3 Reliability section below)
\*\* 1.9s with `/no_think`, 33–38s without (internal reasoning token generation)

**Key findings:**

1. **Qwen3 8B with `/no_think` is the best performer** at 74.8% accuracy and fast latency — but `/no_think` is absolutely mandatory. Without it, accuracy drops to 45–65% and the model becomes operationally unreliable, frequently timing out even with generous budgets.

2. **Qwen2.5 7B Q5_K_M is the most reliable choice** at 72.5% accuracy with consistent, fast inference (~2.3s/sample). Slightly behind Qwen3+no_think on peak accuracy but much more predictable operationally.

3. **The "always use friendly name" prompt instruction** improves every model by 5–24 percentage points over the default HA prompt. This is the single highest-impact prompt change.

4. **Smaller models are not viable** — Llama 3.2 3B (12–21%) fails basic tasks. Meta-Llama 3.1 8B is borderline (30–54%) and highly prompt-sensitive.

5. **Inventory size degrades accuracy** — all models score 5–15 percentage points lower on the medium tier (88 entities, 104 cases) vs small (34 entities, 80 cases).

---

## Benchmark Setup

### Hardware

- **GPU:** NVIDIA GeForce GTX 1080 (8 GB VRAM) — consumer Pascal-era card
- **CPU:** AMD Ryzen 7 3800X (4 cores allocated to VM)
- **RAM:** 7.8 GiB
- **Inference:** llama.cpp server, fully GPU-offloaded (`ngl=99`)
- **Connection:** Remote via SSH (benchmark orchestrator runs locally, inference on remote host)

### Test Configuration

- **Tiers:** Small (34 entities, 80 test cases) and Medium (88 entities, 104 test cases)
- **Scoring:** Strict multi-dimensional — all of response_type, format_valid, call_count, tool_name, args, and no_hallucinated_tools must pass for a sample to score Correct
- **Runs:** 3 per model/config/tier combination (with exceptions noted for Qwen3)
- **Framework:** [Inspect AI](https://inspect.ai-safety-institute.org.uk/)

### Models Tested

| Model | HF Repo | Quant | Context | Size on disk |
|-------|---------|-------|---------|-------------|
| Qwen3 8B | unsloth/Qwen3-8B-GGUF | Q4_K_M | 22000 | ~5 GB |
| Qwen2.5 7B | bartowski/Qwen2.5-7B-Instruct-GGUF | Q5_K_M | 32768 | ~5.5 GB |
| Qwen2.5 7B | bartowski/Qwen2.5-7B-Instruct-GGUF | Q4_K_M | 32768 | ~4.5 GB |
| Functionary-sm 3.1 | mradermacher/functionary-small-v3.1-i1-GGUF | Q5_K_M | 20000 | ~5.5 GB |
| Functionary-sm 3.1 | mradermacher/functionary-small-v3.1-i1-GGUF | Q4_K_M | 24000 | ~4.5 GB |
| Meta-Llama 3.1 8B | bartowski/Meta-Llama-3.1-8B-Instruct-GGUF | Q4_K_M | 25000 | ~4.5 GB |
| Llama 3.2 3B | bartowski/Llama-3.2-3B-Instruct-GGUF | F16 | 13000 | ~6.4 GB |

### Prompt Configurations

All prompts share the same base HA voice assistant instructions. The 4 configs test incremental prompt engineering:

| Config | Label | Change from Default |
|--------|-------|-------------------|
| 1 | **Default** | Stock HA prompt: "prefer passing just name and domain" |
| 2 | **Always Name** | Changed to: "always pass the friendly name from `names:`" |
| 3 | **+ /no_think** | Config 2 wording + `/no_think` appended (suppresses Qwen3 reasoning) |
| 4 | **+ Sensor Hint** | Config 3 + "Prefer HassGetState for sensor/binary_sensor state queries..." |

### Full Prompt Text

Each config modifies only the system prompt instructions block. The entity inventory, tool definitions, and timestamp are appended identically across all configs (see `docs/ha-prompt-reference.md` for full prompt structure). Lines that differ from the Default config are marked with `>>>`.

**Config 1 — Default** (stock HA prompt from `helpers/llm.py`):
```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
When controlling a device, prefer passing just name and domain.
When controlling an area, prefer passing just area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
```

**Config 2 — Always Name** (one line changed):
```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
>>> When controlling a device, always pass the friendly name from `names:` and the domain.
When controlling an area, prefer passing just area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
```

**Config 3 — + /no_think** (two lines changed, one line added):
```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
>>> When controlling a specific device, always use the friendly name from `names:` and the domain.
>>> When controlling an area, prefer passing just the area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
>>> /no_think
```

**Config 4 — + Sensor Hint** (two lines changed, two lines added):
```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
>>> When controlling a specific device, always use the friendly name from `names:` and the domain.
>>> When controlling an area, prefer passing just the area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
>>> Prefer HassGetState for sensor and binary_sensor state queries, and for checking the state of locks, covers, and media players.
>>> /no_think
```

---

## Detailed Results by Tier

### Small Tier (34 entities, 80 test cases)

| Model | Default | Always Name | + /no_think | + Sensor | Latency |
|-------|--------:|------------:|------------:|---------:|--------:|
| **Qwen3 8B** | 58.8%\* | 67.8% | **81.7%** | 77.1% | 1.7s / 37.0s\*\* |
| **Qwen2.5 7B Q5** | 65.0% | 74.6% | 76.7% | 75.4% | 1.9s |
| Qwen2.5 7B Q4 | 57.9% | 67.1% | 67.5% | 67.9% | 1.8s |
| Functionary Q5 | 58.3% | 65.0% | 66.2% | 64.6% | 1.3s |
| Functionary Q4 | 50.8% | 61.2% | 60.0% | 61.2% | 1.1s |
| Meta-Llama 3.1 8B | 28.3% | 57.1% | 50.4% | 45.4% | 1.5s |
| Llama 3.2 3B | 14.6% | 25.0% | 23.8% | 23.8% | 1.6s |

### Medium Tier (88 entities, 104 test cases)

| Model | Default | Always Name | + /no_think | + Sensor | Latency |
|-------|--------:|------------:|------------:|---------:|--------:|
| **Qwen3 8B** | 42.0% | 62.0% | **69.5%** | 69.5% | 2.1s / 38.0s\*\* |
| **Qwen2.5 7B Q5** | 62.2% | 67.0% | 69.2% | 68.3% | 2.6s |
| Qwen2.5 7B Q4 | 56.1% | 65.7% | 64.4% | 66.3% | 2.4s |
| Functionary Q5 | 49.4% | 58.7% | 57.7% | 52.6% | 1.4s |
| Functionary Q4 | 45.5% | 57.7% | 56.7% | 55.1% | 1.2s |
| Meta-Llama 3.1 8B | 31.7% | 51.9% | 46.5% | 42.3% | 1.6s |
| Llama 3.2 3B | 10.6% | 18.6% | 15.7% | 17.3% | 1.8s |

\* n=1 (only 1 clean run achieved — see Qwen3 Reliability section)
\*\* Latency without `/no_think` / with `/no_think`

---

## Test Type Breakdown

The benchmark covers 25 intent types grouped into 6 categories:

### Test Type Inventory

| Category | Intent Type | Small | Medium | Description |
|----------|-------------|------:|-------:|-------------|
| Device Control | light_control | 6 | 7 | Turn lights on/off, set brightness |
| Device Control | fan_control | 4 | 5 | Turn fans on/off, set speed |
| Device Control | cover_control | 3 | 4 | Open/close covers, blinds, garage doors |
| Device Control | switch_control | 2 | 3 | Turn switches on/off |
| Device Control | lock_control | 2 | 2 | Lock/unlock (uses HassTurnOn/Off) |
| Device Control | climate_control | 3 | 4 | Turn thermostats on/off, set temperature |
| Device Control | valve_control | — | 2 | Open/close valves |
| Media | media_control | 11 | 11 | Play/pause/skip, volume, source selection |
| Queries | state_query | 10 | 18 | Check device/sensor state (HassGetState) |
| Queries | climate_query | 1 | 1 | Check thermostat temperature |
| Queries | weather | 1 | 1 | Weather queries |
| Queries | general_knowledge | 2 | 2 | Non-HA knowledge questions |
| Area/Multi | area_command | 1 | 2 | "Turn off all lights in the kitchen" |
| Area/Multi | multi_action | 2 | 3 | Multiple tool calls in one utterance |
| Conversation | conversational | 4 | 4 | Greetings, small talk (should not call tools) |
| Conversation | out_of_scope | 4 | 4 | Requests HA can't handle (should refuse) |
| Conversation | gibberish | 1 | 1 | Nonsense input |
| Conversation | incomplete_command | 3 | 3 | Vague commands requiring clarification |
| Advanced | disambiguation | 4 | 7 | Multiple matching entities, context needed |
| Advanced | implicit_intent | 3 | 6 | Intent must be inferred ("it's cold in here") |
| Advanced | edge_case | 5 | 5 | Unusual phrasings, boundary conditions |
| Advanced | tool_limitation | 2 | 2 | Requests beyond current tool capabilities |
| Advanced | utility | 4 | 4 | Timers, reminders, shopping list |
| Advanced | todo | 2 | 2 | Add/manage to-do items |
| Advanced | vacuum_control | — | 1 | Start/stop vacuum |

### Best Configuration per Model

| Model | Best Config | Overall Accuracy |
|-------|-------------|----------------:|
| Qwen3 8B | + /no_think | 74.8% |
| Qwen2.5 7B Q5 | + /no_think | 72.5% |
| Qwen2.5 7B Q4 | + Sensor | 67.0% |
| Func-sm 3.1 Q5 | Always Name | 61.4% |
| Func-sm 3.1 Q4 | Always Name | 59.2% |
| Meta-Llama 3.1 8B | Always Name | 54.2% |
| Llama 3.2 3B | Always Name | 21.4% |

### Per-Type Accuracy — Small Tier (Best Config per Model)

| Intent Type | Qwen3 8B | Qwen2.5 Q5 | Qwen2.5 Q4 | Func Q5 | Func Q4 | Llama 3.1 | Llama 3.2 |
|-------------|------:|------:|------:|------:|------:|------:|------:|
| light_control | 83% | 83% | 83% | 50% | 61% | 67% | 11% |
| fan_control | 100% | 100% | 83% | 67% | 67% | 75% | 17% |
| cover_control | 100% | 78% | 67% | 33% | 56% | 78% | 0% |
| switch_control | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| lock_control | 100% | 100% | 83% | 83% | 50% | 83% | 0% |
| climate_control | 100% | 100% | 100% | 67% | 67% | 89% | 0% |
| media_control | 91% | 94% | 88% | 73% | 70% | 82% | 61% |
| state_query | 60% | 50% | 27% | 90% | 67% | 63% | 0% |
| climate_query | 100% | 33% | 0% | 33% | 0% | 33% | 0% |
| weather | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| general_knowledge | 100% | 100% | 100% | 100% | 100% | 0% | 0% |
| area_command | 100% | 33% | 33% | 67% | 33% | 33% | 100% |
| multi_action | 100% | 100% | 83% | 50% | 33% | 50% | 50% |
| conversational | 100% | 100% | 100% | 100% | 100% | 33% | 25% |
| out_of_scope | 50% | 50% | 50% | 8% | 8% | 0% | 0% |
| gibberish | 100% | 67% | 0% | 100% | 100% | 100% | 0% |
| incomplete_command | 67% | 67% | 67% | 100% | 100% | 0% | 0% |
| disambiguation | 100% | 75% | 50% | 58% | 58% | 67% | 42% |
| implicit_intent | 33% | 11% | 0% | 0% | 0% | 0% | 0% |
| edge_case | 47% | 47% | 60% | 0% | 0% | 0% | 0% |
| tool_limitation | 50% | 83% | 50% | 50% | 50% | 50% | 0% |
| utility | 100% | 100% | 100% | 100% | 100% | 100% | 67% |
| todo | 100% | 100% | 100% | 100% | 100% | 100% | 83% |

### Per-Type Accuracy — Medium Tier (Best Config per Model)

| Intent Type | Qwen3 8B | Qwen2.5 Q5 | Qwen2.5 Q4 | Func Q5 | Func Q4 | Llama 3.1 | Llama 3.2 |
|-------------|------:|------:|------:|------:|------:|------:|------:|
| light_control | 71% | 86% | 86% | 57% | 57% | 62% | 14% |
| fan_control | 80% | 80% | 73% | 27% | 40% | 20% | 27% |
| cover_control | 100% | 100% | 100% | 58% | 75% | 67% | 25% |
| switch_control | 67% | 100% | 100% | 67% | 56% | 89% | 22% |
| lock_control | 100% | 83% | 33% | 67% | 83% | 33% | 0% |
| climate_control | 100% | 75% | 100% | 92% | 67% | 92% | 25% |
| valve_control | 100% | 100% | 100% | 33% | 33% | 83% | 0% |
| media_control | 91% | 64% | 73% | 70% | 79% | 82% | 36% |
| state_query | 54% | 54% | 46% | 81% | 70% | 61% | 2% |
| climate_query | 100% | 0% | 0% | 0% | 0% | 0% | 0% |
| weather | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| general_knowledge | 100% | 100% | 100% | 100% | 100% | 0% | 0% |
| area_command | 33% | 100% | 83% | 33% | 0% | 17% | 33% |
| multi_action | 67% | 44% | 44% | 11% | 22% | 56% | 33% |
| conversational | 100% | 83% | 100% | 100% | 100% | 50% | 25% |
| out_of_scope | 50% | 75% | 50% | 8% | 8% | 0% | 0% |
| gibberish | 100% | 0% | 33% | 100% | 67% | 100% | 0% |
| incomplete_command | 67% | 100% | 67% | 100% | 89% | 0% | 0% |
| disambiguation | 62% | 71% | 67% | 52% | 52% | 33% | 24% |
| implicit_intent | 17% | 6% | 0% | 0% | 0% | 0% | 0% |
| edge_case | 27% | 33% | 47% | 0% | 0% | 0% | 0% |
| tool_limitation | 50% | 100% | 50% | 33% | 50% | 100% | 0% |
| utility | 100% | 100% | 100% | 92% | 100% | 100% | 67% |
| todo | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| vacuum_control | 33% | 100% | 100% | 100% | 100% | 100% | 0% |

### Notable Patterns by Intent Type

**Near-universal success (all models ≥80% at small):** switch_control, weather, utility, todo. These are simple, well-defined intents with unambiguous tool mappings.

**Near-universal failure:** implicit_intent (0–33%) and edge_case (0–60%). These require inferring user intent from indirect language ("it's cold in here" → turn up thermostat) — a capability gap across all tested models at this parameter size.

**Surprising Functionary advantage:** state_query — Functionary Q5 scores 90% small / 81% medium, significantly outperforming Qwen3 (60%/54%) and Qwen2.5 Q5 (50%/54%). Functionary's tool-calling fine-tuning appears to give it an edge on HassGetState queries specifically.

**out_of_scope is universally hard:** Most models score 0–50%. Correctly *not* calling tools when the user asks something HA can't do requires robust refusal behavior that smaller models lack.

**Qwen3 dominates disambiguation:** 100% at small tier vs 58–75% for other models. The larger reasoning capacity (even with `/no_think`) helps resolve ambiguous entity references.

### Config Impact by Intent Type — Qwen3 8B (Small Tier)

| Intent Type | Default | Always Name | + /no_think | + Sensor |
|-------------|--------:|------------:|------------:|---------:|
| light_control | 50% | 71% | 83% | 83% |
| fan_control | 50% | 69% | 100% | 100% |
| cover_control | 100% | 100% | 100% | 100% |
| switch_control | 50% | 75% | 100% | 100% |
| lock_control | 50% | 100% | 100% | 100% |
| climate_control | 67% | 100% | 100% | 89% |
| media_control | 91% | 91% | 91% | 91% |
| state_query | 40% | 48% | 60% | 63% |
| conversational | 50% | 50% | 100% | 100% |
| disambiguation | 50% | 62% | 100% | 58% |
| implicit_intent | 33% | 25% | 33% | 33% |
| edge_case | 60% | 45% | 47% | 40% |

The `/no_think` effect on Qwen3 is dramatic and broad — it improves nearly every device control type from 50% to 100%, and fixes conversational/disambiguation handling completely. The default prompt with thinking enabled hurts structured output generation.

### Config Impact by Intent Type — Qwen2.5 7B Q5 (Small Tier)

| Intent Type | Default | Always Name | + /no_think | + Sensor |
|-------------|--------:|------------:|------------:|---------:|
| light_control | 67% | 83% | 83% | 83% |
| fan_control | 83% | 100% | 100% | 92% |
| lock_control | 50% | 100% | 100% | 100% |
| media_control | 88% | 88% | 94% | 94% |
| state_query | 10% | 27% | 50% | 40% |
| conversational | 75% | 83% | 100% | 92% |
| disambiguation | 75% | 75% | 75% | 58% |
| implicit_intent | 0% | 22% | 11% | 0% |
| edge_case | 47% | 53% | 47% | 47% |

For Qwen2.5, the "always name" prompt drives the biggest gains (lock_control: 50%→100%, state_query: 10%→27%). The `/no_think` directive provides additional state_query improvement (27%→50%) even though Qwen2.5 doesn't have a thinking mode — the token may act as a formatting hint.

---

## Model Analysis

### Qwen3 8B (Q4_K_M) — Best Accuracy, Requires `/no_think`

**Recommendation: Suitable for HA voice — with `/no_think` mandatory.**

Qwen3 is the strongest model tested, reaching 81.7% on small tier and 69.5% on medium with the `/no_think` prompt (config 3). It outperforms all other models at both tiers when configured correctly.

However, Qwen3 has a fundamental operational issue: without `/no_think`, it generates internal "thinking" tokens before responding. This creates two severe problems:
- **Latency explosion:** Average latency goes from 1.7–2.1s/sample to 33–38s/sample — a 20x increase
- **Operational unreliability:** The thinking token count is highly variable. Some samples think briefly, others spiral into long reasoning chains. This caused frequent timeouts even with 120s/sample (9600s total) budgets. Across 10+ attempts to benchmark Qwen3 without `/no_think`, fewer than half completed successfully.

The accuracy difference is also stark: without `/no_think`, accuracy drops to 45.4% (config 1) — the thinking process appears to hurt more than help for structured tool-calling tasks.

**Bottom line:** Qwen3 8B with `/no_think` is the best choice if you want peak accuracy. Without `/no_think` it is not viable for production use on this hardware class.

### Qwen2.5 7B (Q5_K_M) — Best Overall Balance

**Recommendation: Strong choice for HA voice. Most reliable option.**

Consistent 63–76% accuracy across all configs without any operational issues. The Q5_K_M quantization provides measurably better accuracy than Q4_K_M (+5–7 points across configs) at only modest latency cost (2.3s vs 2.1s avg).

Strengths:
- Very consistent across runs (low variance between the 3 runs per config)
- Degrades gracefully with larger inventories (small→medium drop is modest)
- Benefits from prompt improvements but doesn't *depend* on them as heavily as Qwen3

Weaknesses:
- ~2 points behind Qwen3+no_think at peak
- Higher latency than Functionary models (~2.3s vs ~1.3s)

### Qwen2.5 7B (Q4_K_M) — Good Budget Option

**Recommendation: Viable if VRAM is tight or latency matters more than peak accuracy.**

5–7 percentage points behind Q5_K_M across the board, which is a meaningful gap. However, it's faster (~2.1s) and uses less VRAM. If you're running other services on the same GPU, Q4 is a reasonable trade-off.

### Functionary Small 3.1 (Q4_K_M / Q5_K_M) — Fast but Mid-Tier

**Recommendation: Consider if latency is the primary constraint.**

The Functionary models are the fastest tested (1.1–1.4s/sample) but cap out at ~58–66% accuracy. The Q5 quant is consistently better than Q4 by 3–6 points. Both benefit significantly from the "always name" prompt.

Main weakness: response_type and call_count failures are proportionally high, suggesting the model struggles with deciding *when* to call tools vs. respond with text.

### Meta-Llama 3.1 8B (Q4_K_M) — Highly Prompt-Sensitive

**Recommendation: Not recommended. Too sensitive to prompt wording.**

The most prompt-sensitive model tested: accuracy ranges from 30% (default prompt) to 54% (always-name prompt) — a 24-point swing. This means small prompt changes during HA updates could cause major regressions.

Interestingly, the "always name" prompt (config 2) is Meta-Llama's best config, while `/no_think` and sensor hints actually *hurt* it (54% → 48% → 44%). This is unusual — `/no_think` is a Qwen-specific directive that other models may interpret as a confusing instruction.

The dominant failure mode is `args` failures — the model picks the right intent but passes wrong entity names or domains.

### Llama 3.2 3B (F16) — Not Viable

**Recommendation: Not suitable for HA voice intents.**

At 12–25% accuracy, this model fails more tasks than it succeeds. Even at full F16 precision (no quantization), the 3B parameter count is simply insufficient for the structured tool-calling required by HA intents. The dominant failures span all dimensions — wrong tools, wrong arguments, wrong call counts, and frequent failures to call tools at all.

Included as a lower-bound reference point. Not recommended for any HA voice deployment.

---

## Failure Pattern Analysis

Averaged across all models and configs, the most common failure dimensions are:

| Dimension | Avg failures per run | Impact |
|-----------|--------------------:|--------|
| **args** | 30.0 | Wrong entity name, domain, or argument value |
| **call_count** | 17.3 | Wrong number of tool calls (usually too many or zero) |
| **response_type** | 15.1 | Called tools when shouldn't have, or vice versa |
| **tool_name** | 10.5 | Wrong intent tool selected |
| **format_valid** | 0.0 | Malformed JSON (essentially never happens) |
| **no_hallucinated_tools** | 0.0 | Invented tool names (essentially never happens) |

The `args` dimension dominates failures across all models. The most common sub-pattern is using entity IDs (`light.kitchen_ceiling`) instead of friendly names (`Kitchen Ceiling Light`) — exactly the failure the "always use friendly name" prompt was designed to mitigate, and the data confirms it works.

---

## Prompt Engineering Impact

The progression across the 4 prompt configs reveals clear patterns:

### "Always use friendly name" (Config 1 → 2): +5 to +24 points

The single most impactful change. Every model improves, with the largest gains for models that were defaulting to entity IDs (Meta-Llama: +24 points, Functionary Q4: +11 points).

### Adding `/no_think` (Config 2 → 3): Qwen3-specific

For Qwen3: massive improvement (+9 points accuracy, 20x latency reduction). For other models: neutral to slightly negative (Meta-Llama drops 6 points). This is a model-specific directive that should only be used with Qwen3.

### Adding sensor hint (Config 3 → 4): Marginal to negative

The "Prefer HassGetState for sensor queries" instruction shows mixed results: Qwen2.5 Q4 gains slightly (+1 point), but Functionary Q5 drops 4 points and Meta-Llama drops another 5. The added prompt complexity may confuse smaller models more than it helps.

**Recommended prompt strategy:**
- **Qwen3:** Use config 3 (always name + `/no_think`)
- **All other models:** Use config 2 (always name, no `/no_think`)
- Config 4's sensor hint is not recommended — too model-specific to be safe as a default

---

## Qwen3 Reliability: Without `/no_think`

This section documents the operational reliability issues encountered when benchmarking Qwen3 8B without the `/no_think` directive (configs 1 and 2).

### The problem

Qwen3 generates internal reasoning (thinking) tokens before producing its response. The token count is unpredictable — varying from hundreds to tens of thousands per sample. This creates:

- **Extreme latency variance:** The same model on the same hardware produces per-sample times ranging from <5s to >120s
- **Frequent timeouts:** Even with a 120s/sample budget (9600s for 80 samples), the small tier timed out in the majority of attempts

### Attempt history

| Config | Tier | Attempts | Completions | Success rate |
|--------|------|----------|-------------|-------------|
| Config 1 (Default) | small | 6 | 1 | 17% |
| Config 1 (Default) | medium | 6 | 3 | 50% |
| Config 2 (Always Name) | small | 6 | 4 | 67% |
| Config 2 (Always Name) | medium | 6 | 2 | 33% |

Successful completion times varied wildly even across clean runs — medium tier ranged from 1877s to 5789s for the same 104 samples.

### With `/no_think` (configs 3 and 4)

Zero timeouts across 12 runs (6 per config). Average latency: 1.7–2.1s/sample. Completely stable. The thinking token suppression eliminates both the latency and reliability problems.

### Recommendation

`/no_think` should be considered mandatory for any Qwen3 deployment on consumer hardware (GTX 1080 class). The thinking mode may have value on faster hardware with higher timeout budgets, but on VRAM-constrained GPUs it renders the model impractical.

---

## Inventory Size Sensitivity

All models show accuracy degradation as the entity inventory grows from small (34 entities) to medium (88 entities):

| Model | Small Avg | Medium Avg | Drop |
|-------|----------:|-----------:|-----:|
| Qwen3 8B (/no_think) | 81.7% | 69.5% | -12.2 |
| Qwen2.5 7B Q5 | 72.9% | 66.7% | -6.2 |
| Qwen2.5 7B Q4 | 65.1% | 63.1% | -2.0 |
| Functionary Q5 | 63.5% | 54.6% | -8.9 |
| Functionary Q4 | 58.3% | 53.8% | -4.5 |
| Meta-Llama 3.1 8B | 45.3% | 43.1% | -2.2 |
| Llama 3.2 3B | 21.8% | 15.6% | -6.2 |

(Averages across configs 2–4 only, excluding config 1 where Qwen3 data is incomplete)

Qwen3 shows the largest absolute drop (-12.2 points) but starts from the highest baseline. All models produce more `args` failures as entity count increases — the larger inventory introduces more entity name confusion and ambiguity.

Real-world HA installations typically have 50–200+ entities, placing them in the medium-to-large range. The medium tier results are likely more representative of production accuracy than small tier.

---

## Methodology Notes

- **Scoring is strict:** A sample is only Correct if ALL dimensions pass (response_type, format_valid, call_count, tool_name, args, no_hallucinated_tools). This means the reported accuracy is a lower bound — many "incorrect" samples have the right intent but a wrong argument detail.
- **3 runs per configuration** for statistical validity. Run-to-run variance was generally low (1–5 percentage points) for all models except Qwen3 without `/no_think`.
- **Qwen3 configs 1 & 2** have reduced sample sizes due to timeout failures (n=1 for some tier/config combinations). These results are reported but should be interpreted with appropriate caution.
- **Warmup:** Each model was warmed up with 5 inference calls before benchmark timing began, to prime GPU kernels and KV cache.
- **Serial execution:** All benchmarks used `--max-connections 1` to ensure accurate per-sample latency measurement.
- **No seed pinning:** Runs used non-deterministic sampling to capture natural variance. The low run-to-run variance suggests results are robust.

---

## Recommendations for HA Users

### If you have a GTX 1080 (8GB) or similar

1. **Best accuracy:** Qwen3 8B Q4_K_M with `/no_think` in the system prompt (74.8% small, 69.5% medium)
2. **Best reliability:** Qwen2.5 7B Q5_K_M (72.5% small, 69.2% medium) — no special prompt needed beyond "always use friendly name"
3. **Best latency:** Functionary Small 3.1 Q4_K_M (~1.2s/sample, 58% accuracy) — viable if you prioritize response speed

### Prompt recommendations

- Add "always pass the friendly name from `names:`" to your system prompt — this is the single most impactful change
- If using Qwen3: append `/no_think` to the system prompt (mandatory)
- Avoid adding model-specific instructions (sensor hints, etc.) unless you've tested them with your specific model

### What doesn't work

- Llama 3.2 3B: too small for structured tool calling
- Meta-Llama 3.1 8B: too prompt-sensitive for reliable deployment
- Qwen3 without `/no_think`: operationally unreliable on consumer GPUs

---

## Raw Data Reference

All benchmark data is in `logs/benchmark/benchmark_test_{1,2,3,4}/`. Each run directory contains:
- `orchestration.log` — server lifecycle, timing, errors
- Per-model subdirectories with `.eval` files (Inspect AI zip archives containing per-sample JSON)
- `hw_info.json` — hardware snapshot at run time

For the extraction script and per-run details, see `docs/benchmark-run-inventory.md` (internal).
