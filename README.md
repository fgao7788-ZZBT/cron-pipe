# 🚰 cron-pipe

Turn dumb cron jobs into state-aware, conditional pipelines.

A zero-dependency, ultra-lightweight Python tool that connects isolated cron jobs using State JSON files. It turns isolated scripts into a gated pipeline, saving computing resources and API costs.

---

## 🤔 The Problem

We all love cron for scheduling background scripts. But as your system grows, cron's lack of state awareness becomes a massive pain:

- **Wasted Resources:** Your downstream scripts run at fixed intervals, even when there's no new data from the upstream script. (Wasting CPU, API limits, and LLM tokens).
- **The Communication Gap:** If Script A (data fetcher) finishes, how does Script B (analyzer) know it's time to run? You usually end up writing messy inter-process communication or database flags.

## 💡 The Solution

`cron-pipe` generates boilerplate code to connect your cron jobs via **State JSON Files**. It acts as a strict "Gatekeeper".

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Cron 14:25     │────▶│  state.json  │◀────│  Cron 14:49      │
│  Upstream       │     └──────┬───────┘     │  Downstream      │
│  (Writer)       │            │              │  (Reader/Gate)   │
└─────────────────┘     ┌──────┴───────┐     └──────────────────┘
                         │ Gate Open?   │
                         │  (PROCEED?)  │
                         └──────┬───────┘
                          ┌─────┴─────┐
                          │ Yes │  No │
                          │     │     │
                          ▼     ▼     ▼
                     ┌────────┐ ┌──────────┐
                     │  Run   │ │ Exit (0) │
                     │ Logic  │ │ Silent   │
                     └────────┘ └──────────┘
```

## 🚀 Quick Start

Install via pip:

```bash
pip install cron-pipe
```

Generate a writer/reader pair instantly:

```bash
cron-pipe init --writer scan.py --reader decider.py
```

This generates two Python scripts with the cron-pipe pattern already implemented.

## 🛠️ Usage

### 1. The Upstream (Writer)

Evaluates the environment and sets a state.

```python
from cron_pipe import StateWriter

state = StateWriter("/tmp/daily_pipeline_state.json")
score = 0.85  # Your upstream logic calculates this...

if score > 0.6:
    state.set("PROCEED", score=score, metrics={"volatility": "high"})
else:
    state.set("HALT", reason="Market is dead water")
```

### 2. The Downstream (Reader / Gatekeeper)

Checks the state before running expensive logic.

```python
from cron_pipe import StateGate

gate = StateGate("/tmp/daily_pipeline_state.json")

# Exits silently (sys.exit(0)) if action is "HALT"
# Also checks if the state file is older than 3600 seconds (stale prevention)
gate.require_proceed(max_age_seconds=3600)

# You can also pass a threshold if your writer provided a score
# gate.require_proceed(threshold=0.8)

# --- Your expensive/LLM logic runs ONLY if the gate is open ---
print("Gate is open! Running heavy analysis...")
```

### Fail-Open Safety

`cron-pipe` is designed with a **Fail-Open** philosophy. If the state file is missing or corrupted, it prints a warning to stderr but allows the downstream script to proceed. We prefer false positives over a completely blocked pipeline.

### Stale State Prevention

State files include an ISO 8601 timestamp. The reader can reject state older than `max_age_seconds`, preventing downstream scripts from acting on stale data after the upstream has stopped writing.

## 📖 Case Study: Why I Built This

I developed `cron-pipe` while building an **Autonomous AI Quantitative Trading System** for the A-Share market.

I had a pipeline where a heavy LLM agent (DeepSeek V4) analyzed market sentiment every few minutes near market close. However, 80% of the time, the market was "dead water" (low volatility), and calling the LLM API was a massive waste of tokens.

By using `cron-pipe`:

- A lightweight Python script (runs via cron at 14:25) calculates market volatility locally (**0 tokens**).
- It writes the status to a `daily_market_state.json`.
- The heavy LLM trading agent (runs via cron at 14:49) uses `StateGate`. If the market is dead, it exits instantly.

This simple pattern saved me **~100K tokens daily** while keeping the architecture decoupled.

## 🤝 Let's Connect

I regularly share insights on Python engineering, Multi-Agent architectures, and Quantitative Trading.

- **𝕏 (Twitter):** [@YOUR_HANDLE](https://twitter.com/YOUR_HANDLE)
- **Blog:** [YOUR_BLOG_URL](YOUR_BLOG_URL)

## License

MIT
