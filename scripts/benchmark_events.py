"""Timestamp clustering for offline wake-word benchmark reports."""

from collections.abc import Iterable


def clustered_count(indices: list[int], tolerance_predictions: int) -> int:
    """Count clusters whose successive detections are at most tolerance apart."""
    if not indices:
        return 0
    ordered = sorted(indices)
    clusters = 1
    cluster_end = ordered[0]
    for index in ordered[1:]:
        if index - cluster_end > tolerance_predictions:
            clusters += 1
        cluster_end = index
    return clusters


def combined_counts(model_events: Iterable[list[int]], tolerance_predictions: int) -> dict[str, int]:
    """Merge model detections from one recording, never from separate channels."""
    events = [event for indices in model_events for event in indices]
    return {
        "raw_model_detections": len(events),
        "events": clustered_count(events, tolerance_predictions),
    }
