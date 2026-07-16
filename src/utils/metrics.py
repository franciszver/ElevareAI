"""
Metrics Collection Utilities
Collect and track application metrics
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Simple in-memory metrics collector

    For production, consider using:
    - CloudWatch (AWS)
    - Prometheus + Grafana
    - Datadog
    - New Relic
    """

    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._gauges: Dict[str, float] = {}
        self._errors: List[Dict] = []
        self._max_error_history = 100

    def increment(
        self, metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric

        Args:
            metric_name: Name of the metric
            value: Amount to increment (default: 1)
            tags: Optional tags for filtering
        """
        key = self._build_key(metric_name, tags)
        self._counters[key] += value
        logger.debug(f"Metric incremented: {key} = {self._counters[key]}")

    def record_timing(
        self, metric_name: str, duration: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a timing metric

        Args:
            metric_name: Name of the metric
            duration: Duration in seconds
            tags: Optional tags for filtering
        """
        key = self._build_key(metric_name, tags)
        self._timers[key].append(duration)

        # Keep only last 1000 timings per metric
        if len(self._timers[key]) > 1000:
            self._timers[key] = self._timers[key][-1000:]

        logger.debug(f"Timing recorded: {key} = {duration:.3f}s")

    def set_gauge(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge metric (current value)

        Args:
            metric_name: Name of the metric
            value: Current value
            tags: Optional tags for filtering
        """
        key = self._build_key(metric_name, tags)
        self._gauges[key] = value
        logger.debug(f"Gauge set: {key} = {value}")

    def record_error(
        self, error_type: str, error_message: str, context: Optional[Dict] = None
    ) -> None:
        """
        Record an error

        Args:
            error_type: Type of error (e.g., "ValidationError", "DatabaseError")
            error_message: Error message
            context: Additional context
        """
        error_record = {
            "type": error_type,
            "message": error_message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._errors.append(error_record)

        # Keep only last N errors
        if len(self._errors) > self._max_error_history:
            self._errors = self._errors[-self._max_error_history :]

        self.increment("errors", tags={"type": error_type})
        logger.error(f"Error recorded: {error_type} - {error_message}")

    def get_counter(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> int:
        """Get counter value"""
        key = self._build_key(metric_name, tags)
        return self._counters.get(key, 0)

    def get_timing_stats(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get timing statistics"""
        key = self._build_key(metric_name, tags)
        timings = self._timers.get(key, [])

        if not timings:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_timings = sorted(timings)
        count = len(sorted_timings)

        return {
            "count": count,
            "min": min(sorted_timings),
            "max": max(sorted_timings),
            "avg": sum(sorted_timings) / count,
            "p50": sorted_timings[int(count * 0.50)],
            "p95": sorted_timings[int(count * 0.95)]
            if count > 1
            else sorted_timings[0],
            "p99": sorted_timings[int(count * 0.99)]
            if count > 1
            else sorted_timings[0],
        }

    def get_gauge(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """Get gauge value"""
        key = self._build_key(metric_name, tags)
        return self._gauges.get(key)

    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent errors"""
        return self._errors[-limit:]

    def get_all_metrics(self) -> Dict:
        """Get all metrics (for debugging/monitoring)"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timings": {
                key: self.get_timing_stats(key.split(":")[0])
                for key in self._timers.keys()
            },
            "recent_errors": self.get_recent_errors(10),
        }

    def _build_key(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> str:
        """Build cache key from metric name and tags"""
        if not tags:
            return metric_name

        tag_str = ":".join([f"{k}={v}" for k, v in sorted(tags.items())])
        return f"{metric_name}:{tag_str}"

    def reset(self) -> None:
        """Reset all metrics (for testing)"""
        self._counters.clear()
        self._timers.clear()
        self._gauges.clear()
        self._errors.clear()


# Global metrics collector instance
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance"""
    return _metrics


# Convenience functions
def increment_counter(
    metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
) -> None:
    """Increment a counter metric"""
    _metrics.increment(metric_name, value, tags)


def record_timing(
    metric_name: str, duration: float, tags: Optional[Dict[str, str]] = None
) -> None:
    """Record a timing metric"""
    _metrics.record_timing(metric_name, duration, tags)


def set_gauge(
    metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
) -> None:
    """Set a gauge metric"""
    _metrics.set_gauge(metric_name, value, tags)


def record_error(
    error_type: str, error_message: str, context: Optional[Dict] = None
) -> None:
    """Record an error"""
    _metrics.record_error(error_type, error_message, context)


# Context manager for timing
class TimingContext:
    """Context manager for timing code blocks"""

    def __init__(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        self.metric_name = metric_name
        self.tags = tags
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        record_timing(self.metric_name, duration, self.tags)
        return False
