import unittest

from scripts.benchmark_events import clustered_count, combined_counts


class BenchmarkEventsTests(unittest.TestCase):
    def test_empty_and_single_detection(self):
        self.assertEqual(clustered_count([], 33), 0)
        self.assertEqual(clustered_count([100], 33), 1)

    def test_overlap_boundary_and_separate_events(self):
        # Same prediction and exactly 990 ms merge; 1020 ms starts a new event.
        self.assertEqual(clustered_count([100, 100, 133, 167], 33), 2)

    def test_successive_overlap_can_form_a_longer_chain(self):
        self.assertEqual(clustered_count([166, 100, 133], 33), 1)

    def test_four_models_merge_and_keep_raw_count(self):
        models = [[100, 400], [100], [125], [200]]
        self.assertEqual(combined_counts(models, 33), {"raw_model_detections": 5, "events": 3})
        self.assertEqual(models, [[100, 400], [100], [125], [200]])

    def test_recordings_are_counted_separately(self):
        first = combined_counts([[100], [100], [], []], 33)
        second = combined_counts([[100], [], [100], []], 33)
        self.assertEqual(first["events"] + second["events"], 2)


if __name__ == "__main__":
    unittest.main()
