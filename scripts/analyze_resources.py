#!/usr/bin/env python3
"""Summarize a serial/API resource log: analyze_resources.py capture.log.

Use one capture per workload. Only complete resource rows are accepted; boot
messages, sensor DEBUG output and other firmware logs are ignored.
"""
import argparse
import json
import math
import re
import statistics
from pathlib import Path

FIELDS = (
    "internal_free_B", "internal_min_B", "internal_block_B",
    "psram_free_B", "psram_min_B", "psram_block_B", "loop_max_ms",
    "cpu0_busy_pct", "cpu1_busy_pct", "cpu_mean_busy_pct",
)
MEMORY_FIELDS = FIELDS[:7]
CPU_FIELDS = FIELDS[7:]
VALUE = re.compile(r"\b([a-zA-Z0-9_]+)=(-?\d+(?:\.\d+)?)\b")


def summarize(text):
    samples = {field: [] for field in FIELDS}
    task_stacks = {}
    for line in text.splitlines():
        if "[resources:" not in line:
            continue
        values = dict(VALUE.findall(line))
        for group in (MEMORY_FIELDS, CPU_FIELDS):
            if all(field in values for field in group):
                for field in group:
                    samples[field].append(float(values[field]))
        task = re.search(r"\btask=(\S+)\s+stack_min_free_B=(\d+)", line)
        if task:
            name, size = task.group(1), int(task.group(2))
            task_stacks[name] = min(size, task_stacks.get(name, size))
    result = {}
    for field, values in samples.items():
        if values:
            ordered = sorted(values)
            result[field] = {
                "samples": len(values), "min": min(values),
                "median": statistics.median(values),
                "p95": ordered[math.ceil(len(values) * 0.95) - 1],
                "max": max(values),
            }
    return {"metrics": result, "task_stack_min_free_B": task_stacks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    result = summarize(args.log.read_text(errors="replace"))
    if not result["metrics"]:
        parser.error("No complete resource measurements found in this log")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
