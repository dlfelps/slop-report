"""Vibes Check: a completely useless metric that rates how the code 'feels'."""

import hashlib

from src.report import MetricResult

_VIBES = [
    ("Immaculate", "✅", "The code radiates a calm, confident energy. Chef's kiss."),
    ("Good", "✅", "Solid vibes detected. The linter can feel your good intentions."),
    ("Meh", "⚠️", "The code compiles, but it seems a little tired. Maybe add a comment?"),
    ("Chaotic", "⚠️", "Something in here is screaming. Not sure what, but it's screaming."),
    ("Off", "📉", "The vibes are off. No further information is available at this time."),
    ("Cursed", "📉", "This diff has been blessed by neither the compiler nor the ancient ones."),
]


def _vibe_index(base_ref: str, workspace: str) -> int:
    """Deterministically pick a vibe from the ref + workspace so it's reproducible."""
    raw = f"{base_ref}:{workspace}"
    digest = hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — not used for security
    return int(digest, 16) % len(_VIBES)


def run(base_ref: str, workspace: str) -> MetricResult:
    """Return a MetricResult describing the current vibes of the PR."""
    label, status, detail = _VIBES[_vibe_index(base_ref, workspace)]
    return MetricResult(
        name="Vibes Check",
        score=label,
        status=status,
        detail=detail,
    )
