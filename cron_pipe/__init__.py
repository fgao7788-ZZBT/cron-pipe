"""cron-pipe — State-aware cron pipelines.

Turn dumb cron jobs into conditional pipelines using shared state files.
"""

import json
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.0"

logger = logging.getLogger("cron_pipe")


class StateWriter:
    """Write execution state for downstream scripts to read.

    Place this in your upstream (earlier-running) cron script after
    evaluating lightweight conditions. The downstream script uses
    StateGate to decide whether to proceed.

    Usage:
        writer = StateWriter("/path/to/state.json")
        writer.proceed(score=0.82)

    Or as context manager:
        with StateWriter("/path/to/state.json") as w:
            w.halt(reason="low volatility")
    """

    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def set(self, action: str, score: float = None, reason: str = "",
            metrics: dict = None):
        """Write state to the JSON file.

        Args:
            action: Must be ``"PROCEED"`` or ``"HALT"``.
            score: Optional numerical score for threshold gating.
            reason: Human-readable explanation (shown on gate deny).
            metrics: Arbitrary key-value data for downstream scripts.
        """
        if action not in ("PROCEED", "HALT"):
            raise ValueError(f"action must be PROCEED or HALT, got {action!r}")
        state = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if score is not None:
            state["score"] = round(score, 4)
        if reason:
            state["reason"] = reason
        if metrics:
            state["metrics"] = metrics

        self.path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n"
        )

    def proceed(self, score: float = None, metrics: dict = None):
        """Shorthand: set(action='PROCEED', score=score, metrics=metrics)."""
        self.set(action="PROCEED", score=score, metrics=metrics)

    def halt(self, reason: str = "", metrics: dict = None):
        """Shorthand: set(action='HALT', reason=reason, metrics=metrics)."""
        self.set(action="HALT", reason=reason, metrics=metrics)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


class StateGate:
    """Gate a downstream script based on state written by an upstream writer.

    Place this at the very top of your downstream script — *before* any
    expensive imports or logic — so it can exit silently (exit code 0)
    when conditions aren't met, wasting zero resources.

    Usage:
        gate = StateGate("/path/to/state.json")

        # Skip if upstream wrote HALT
        gate.require_proceed()

        # Skip if score < 0.6
        gate.require_proceed(threshold=0.6)

        # Custom condition
        gate.require(lambda s: s.get("metrics", {}).get("vol", 0) > 1.0)
    """

    def __init__(self, path: str, max_age_seconds: int = 3600):
        """Args:
            path: Path to the state JSON file.
            max_age_seconds: Treat state as stale if older than this.
                ``None`` disables the check. Default 3600 (1 hour).
        """
        self.path = Path(path).expanduser().resolve()
        self.max_age_seconds = max_age_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def state(self) -> dict:
        """Load and return current state. Returns ``{}`` on failure."""
        return self._load()

    def require_proceed(self, threshold: float = None,
                        max_age_seconds: int = None):
        """Exit silently unless the upstream wrote ``PROCEED``.

        Args:
            threshold: If set, also requires ``state[\"score\"] >= threshold``.
            max_age_seconds: Per-call override of the instance default.
        """
        if max_age_seconds is not None:
            self.max_age_seconds = max_age_seconds

        state = self._load()
        if not state:
            return  # fail-open: proceed

        action = state.get("action", "")
        if action != "PROCEED":
            reason = state.get("reason", "")
            parts = [f"[cron-pipe] Gate: action={action}"]
            if reason:
                parts.append(f"({reason})")
            self._exit_silently(" ".join(parts))

        if threshold is not None:
            score = state.get("score")
            if score is None:
                self._exit_silently(
                    f"[cron-pipe] Gate: no score in state, threshold={threshold}"
                )
            if score < threshold:
                self._exit_silently(
                    f"[cron-pipe] Gate: score={score} < threshold={threshold}"
                )

    def require(self, condition_fn, error_msg: str = "condition not met"):
        """Exit silently if *condition_fn(state_dict)* returns ``False``.

        Args:
            condition_fn: Callable(state: dict) -> bool.
            error_msg: Description shown on gate deny.
        """
        state = self._load()
        if state and not condition_fn(state):
            self._exit_silently(f"[cron-pipe] Gate: {error_msg}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load and validate state. Returns ``{}`` on failure (fail-open)."""
        try:
            if not self.path.exists():
                self._warn(f"State file not found: {self.path} — proceeding")
                return {}

            raw = self.path.read_text()
            if not raw.strip():
                self._warn(f"State file empty: {self.path} — proceeding")
                return {}

            state: dict = json.loads(raw)

            self._check_staleness(state)

            return state

        except (json.JSONDecodeError, OSError) as exc:
            self._warn(f"State read error: {exc} — proceeding")
            return {}

    def _check_staleness(self, state: dict):
        """Log a warning if the state is stale, but still return it."""
        if self.max_age_seconds is None:
            return
        ts_raw = state.get("timestamp")
        if not ts_raw:
            return
        try:
            age = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(ts_raw)).total_seconds()
            if age > self.max_age_seconds:
                self._warn(
                    f"State stale ({age:.0f}s > {self.max_age_seconds}s)"
                    f" — proceeding"
                )
        except (ValueError, TypeError):
            pass

    def _exit_silently(self, msg: str = ""):
        """Exit code 0 — cron treats this as success, no alert."""
        if msg:
            print(msg)
        sys.exit(0)

    def _warn(self, msg: str):
        logger.warning(msg)
        print(f"[cron-pipe] ⚠️ {msg}", file=sys.stderr)
