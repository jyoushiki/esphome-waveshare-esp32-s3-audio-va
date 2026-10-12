#pragma once

#include "esphome/core/log.h"
#include <esp_heap_caps.h>

#if CONFIG_FREERTOS_GENERATE_RUN_TIME_STATS
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <algorithm>
#include <cmath>

namespace waveshare_diagnostics {

// Keep the task snapshot in PSRAM, rather than consuming an audio task's stack.
// uxTaskGetSystemState suspends scheduling and scans stack watermarks: use this
// optional profiler only for comparisons with identical instrumentation.
class ResourceProfiler {
 public:
  void sample(bool list_tasks = false) {
    if (tasks_ == nullptr) {
      tasks_ = static_cast<TaskStatus_t *>(heap_caps_calloc(CAPACITY, sizeof(TaskStatus_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
      if (tasks_ == nullptr) {
        ESP_LOGW("resources", "Unable to allocate task snapshot in PSRAM");
        return;
      }
    }
    configRUN_TIME_COUNTER_TYPE total = 0;
    const UBaseType_t count = uxTaskGetSystemState(tasks_, CAPACITY, &total);
    if (count == 0) {
      ESP_LOGW("resources", "Task snapshot failed (capacity %u)", unsigned(CAPACITY));
      return;
    }
    configRUN_TIME_COUNTER_TYPE idle[2] = {};
    bool found[2] = {};
    for (UBaseType_t i = 0; i < count; ++i) {
      const auto &task = tasks_[i];
      for (int core = 0; core < 2; ++core) {
        if (task.xHandle == xTaskGetIdleTaskHandleForCore(core)) {
          idle[core] = task.ulRunTimeCounter;
          found[core] = true;
        }
      }
      if (list_tasks) {
        // ESP-IDF reports high-water marks in bytes, unlike vanilla FreeRTOS.
        ESP_LOGI("resources", "task=%s stack_min_free_B=%u priority=%u", task.pcTaskName,
                 unsigned(task.usStackHighWaterMark), unsigned(task.uxCurrentPriority));
      }
    }
    // Skip the initial sample and counter resets/wraps. Each core's idle delta
    // is divided by wall time; average the two busy percentages for total load.
    if (ready_ && found[0] && found[1] && total > previous_total_ &&
        idle[0] >= previous_idle_[0] && idle[1] >= previous_idle_[1]) {
      const double elapsed = double(total - previous_total_);
      for (int core = 0; core < 2; ++core)
        busy[core] = std::clamp(float(100.0 * (1.0 - double(idle[core] - previous_idle_[core]) / elapsed)), 0.0f, 100.0f);
      ESP_LOGI("resources", "cpu0_busy_pct=%.1f cpu1_busy_pct=%.1f cpu_mean_busy_pct=%.1f tasks=%u",
               busy[0], busy[1], (busy[0] + busy[1]) / 2.0f, unsigned(count));
    } else {
      busy[0] = busy[1] = NAN;
    }
    previous_total_ = total;
    previous_idle_[0] = idle[0];
    previous_idle_[1] = idle[1];
    ready_ = found[0] && found[1];
  }
  float busy[2] = {NAN, NAN};

 private:
  static constexpr UBaseType_t CAPACITY = 64;
  TaskStatus_t *tasks_ = nullptr;
  configRUN_TIME_COUNTER_TYPE previous_total_ = 0;
  configRUN_TIME_COUNTER_TYPE previous_idle_[2] = {};
  bool ready_ = false;
};

inline ResourceProfiler &profiler() {
  static ResourceProfiler instance;
  return instance;
}
}  // namespace waveshare_diagnostics
#endif
