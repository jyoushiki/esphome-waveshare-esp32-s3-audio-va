import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "analyze_resources", Path(__file__).parents[1] / "scripts/analyze_resources.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AnalyzeResourcesTests(unittest.TestCase):
    def test_complete_serial_rows_and_stack_minima(self):
        row = "[12:00:00][I][resources:123]: "
        result = module.summarize(
            row + "internal_free_B=120 internal_min_B=90 internal_block_B=50 "
            "psram_free_B=1000 psram_min_B=900 psram_block_B=800 loop_max_ms=3\n"
            + row + "cpu0_busy_pct=30.0 cpu1_busy_pct=70.0 cpu_mean_busy_pct=50.0 tasks=20\n"
            + row + "task=audio_task stack_min_free_B=512 priority=5\n"
            + row + "task=audio_task stack_min_free_B=256 priority=5\n"
        )
        self.assertEqual(result["metrics"]["internal_free_B"]["min"], 120)
        self.assertEqual(result["metrics"]["cpu_mean_busy_pct"]["median"], 50)
        self.assertEqual(result["task_stack_min_free_B"], {"audio_task": 256})


    def test_ignores_partial_rows_and_unrelated_logs(self):
        result = module.summarize(
            "[I][resources:1]: internal_free_B=123\n"
            "[I][other:1]: cpu0_busy_pct=1 cpu1_busy_pct=2 cpu_mean_busy_pct=1.5\n"
        )
        self.assertEqual(result, {"metrics": {}, "task_stack_min_free_B": {}})
