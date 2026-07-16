"""
A/B Testing Framework
Framework for testing nudge variants and other features
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

# Import models - will use test models if available
try:
    from tests.test_models import TestNudge, TestUser

    USE_TEST_MODELS = True
except ImportError:
    USE_TEST_MODELS = False
    from src.models.nudge import Nudge
    from src.models.user import User

logger = logging.getLogger(__name__)


class ABTestingFramework:
    """A/B testing framework for nudges and features"""

    def __init__(self, db: Session):
        self.db = db

    def assign_variant(
        self,
        user_id: str,
        test_name: str,
        variants: List[str],
        weights: Optional[List[float]] = None,
    ) -> str:
        """
        Assign a user to a test variant

        Args:
            user_id: User ID
            test_name: Name of the A/B test
            variants: List of variant names (e.g., ["control", "variant_a", "variant_b"])
            weights: Optional weights for each variant (default: equal distribution)

        Returns:
            Assigned variant name
        """
        if not weights:
            weights = [1.0 / len(variants)] * len(variants)

        if len(weights) != len(variants):
            raise ValueError("Weights must match variants length")

        # Use consistent assignment based on user_id and test_name
        # This ensures the same user always gets the same variant
        random.seed(hash(f"{user_id}_{test_name}"))
        variant = random.choices(variants, weights=weights)[0]

        logger.info(
            f"Assigned user {user_id} to variant {variant} for test {test_name}"
        )
        return variant

    def get_test_results(
        self,
        test_name: str,
        variant_field: str = "type",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Get A/B test results

        Analyzes performance of different variants
        """
        if USE_TEST_MODELS:
            NudgeModel = TestNudge
        else:
            NudgeModel = Nudge

        query = self.db.query(NudgeModel)

        # Filter by test name (stored in trigger_reason or custom field)
        # For now, we'll use type as the variant field
        if start_date:
            query = query.filter(NudgeModel.sent_at >= start_date)
        if end_date:
            query = query.filter(NudgeModel.sent_at <= end_date)

        nudges = query.all()

        # Group by variant
        variant_stats = {}

        for nudge in nudges:
            # Get variant from the specified field
            if variant_field == "type":
                variant = nudge.type
            elif variant_field == "channel":
                variant = nudge.channel
            else:
                variant = "unknown"

            if variant not in variant_stats:
                variant_stats[variant] = {"sent": 0, "opened": 0, "clicked": 0}

            variant_stats[variant]["sent"] += 1
            if nudge.opened_at:
                variant_stats[variant]["opened"] += 1
            if nudge.clicked_at:
                variant_stats[variant]["clicked"] += 1

        # Calculate rates
        results = {}
        for variant, stats in variant_stats.items():
            open_rate = (
                (stats["opened"] / stats["sent"] * 100) if stats["sent"] > 0 else 0
            )
            click_rate = (
                (stats["clicked"] / stats["sent"] * 100) if stats["sent"] > 0 else 0
            )
            click_through_rate = (
                (stats["clicked"] / stats["opened"] * 100) if stats["opened"] > 0 else 0
            )

            results[variant] = {
                "sent": stats["sent"],
                "opened": stats["opened"],
                "clicked": stats["clicked"],
                "open_rate": round(open_rate, 2),
                "click_rate": round(click_rate, 2),
                "click_through_rate": round(click_through_rate, 2),
            }

        # Determine winner (highest click rate)
        winner = (
            max(results.items(), key=lambda x: x[1]["click_rate"]) if results else None
        )

        return {
            "test_name": test_name,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "variants": results,
            "winner": winner[0] if winner else None,
            "total_sent": sum(s["sent"] for s in variant_stats.values()),
            "total_opened": sum(s["opened"] for s in variant_stats.values()),
            "total_clicked": sum(s["clicked"] for s in variant_stats.values()),
        }

    def create_test(
        self,
        test_name: str,
        description: str,
        variants: List[Dict],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Create a new A/B test configuration

        Args:
            test_name: Unique test name
            description: Test description
            variants: List of variant configs [{"name": "control", "weight": 0.5}, ...]
            start_date: Test start date
            end_date: Test end date

        Returns:
            Test configuration
        """
        # In a real implementation, this would store in a database
        # For now, return the configuration
        total_weight = sum(v.get("weight", 1.0) for v in variants)

        return {
            "test_name": test_name,
            "description": description,
            "variants": variants,
            "weights_normalized": [
                v.get("weight", 1.0) / total_weight for v in variants
            ],
            "status": "active",
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "created_at": datetime.utcnow().isoformat(),
        }

    def calculate_statistical_significance(
        self,
        variant_a_clicks: int,
        variant_a_sent: int,
        variant_b_clicks: int,
        variant_b_sent: int,
    ) -> Dict:
        """
        Calculate statistical significance between two variants

        Uses chi-square test for proportions
        """
        if variant_a_sent == 0 or variant_b_sent == 0:
            return {"significant": False, "p_value": 1.0, "confidence_level": 0.0}

        # Calculate conversion rates
        rate_a = variant_a_clicks / variant_a_sent
        rate_b = variant_b_clicks / variant_b_sent

        # Simple z-test approximation
        # For production, use proper statistical library (scipy.stats)
        pooled_rate = (variant_a_clicks + variant_b_clicks) / (
            variant_a_sent + variant_b_sent
        )

        if pooled_rate == 0 or pooled_rate == 1:
            return {"significant": False, "p_value": 1.0, "confidence_level": 0.0}

        se = (
            pooled_rate * (1 - pooled_rate) * (1 / variant_a_sent + 1 / variant_b_sent)
        ) ** 0.5
        z_score = abs(rate_a - rate_b) / se if se > 0 else 0

        # Approximate p-value (for 95% confidence, z > 1.96)
        # This is simplified - use proper statistical test in production
        p_value = 2 * (1 - min(z_score / 1.96, 1.0))
        confidence_level = (1 - p_value) * 100

        return {
            "significant": z_score > 1.96,  # 95% confidence
            "p_value": round(p_value, 4),
            "confidence_level": round(confidence_level, 2),
            "z_score": round(z_score, 3),
            "conversion_rates": {
                "variant_a": round(rate_a * 100, 2),
                "variant_b": round(rate_b * 100, 2),
                "difference": round(abs(rate_a - rate_b) * 100, 2),
            },
        }
