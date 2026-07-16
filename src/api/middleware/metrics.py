"""
Request Metrics Middleware
Track request/response metrics
"""

import logging
import time

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.utils.metrics import TimingContext, get_metrics

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request/response metrics"""

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics"""
        metrics = get_metrics()

        # Skip metrics for health checks and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Extract route info
        route_path = request.url.path
        method = request.method

        # Increment request counter
        metrics.increment("http.requests", tags={"method": method, "path": route_path})

        # Process request
        try:
            with TimingContext(
                "http.request.duration", tags={"method": method, "path": route_path}
            ):
                response = await call_next(request)

            # Record success metrics
            status_code = response.status_code
            duration = time.time() - start_time

            metrics.increment(
                "http.responses",
                tags={
                    "method": method,
                    "path": route_path,
                    "status": str(status_code),
                    "status_class": self._get_status_class(status_code),
                },
            )

            # Record slow requests (>1 second)
            if duration > 1.0:
                metrics.increment(
                    "http.slow_requests", tags={"method": method, "path": route_path}
                )
                logger.warning(
                    f"Slow request: {method} {route_path} took {duration:.3f}s"
                )

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration:.3f}"

            return response

        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time

            metrics.record_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={"method": method, "path": route_path, "duration": duration},
            )

            metrics.increment(
                "http.errors",
                tags={
                    "method": method,
                    "path": route_path,
                    "error_type": type(e).__name__,
                },
            )

            raise

    def _get_status_class(self, status_code: int) -> str:
        """Get HTTP status class (2xx, 3xx, 4xx, 5xx)"""
        if 200 <= status_code < 300:
            return "2xx"
        elif 300 <= status_code < 400:
            return "3xx"
        elif 400 <= status_code < 500:
            return "4xx"
        else:
            return "5xx"
