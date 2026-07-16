"""
Data Exporter
Export data to CSV and JSON formats
"""

import csv
import json
import logging
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataExporter:
    """Export data to various formats"""

    @staticmethod
    def to_csv(
        data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None
    ) -> str:
        """
        Convert list of dictionaries to CSV string

        Args:
            data: List of dictionaries to export
            fieldnames: Optional list of field names (uses dict keys if not provided)

        Returns:
            CSV string
        """
        if not data:
            return ""

        output = StringIO()

        # Get fieldnames
        if not fieldnames:
            fieldnames = list(data[0].keys())

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in data:
            # Convert complex types to strings
            cleaned_row = {}
            for key, value in row.items():
                if value is None:
                    cleaned_row[key] = ""
                elif isinstance(value, (dict, list)):
                    cleaned_row[key] = json.dumps(value)
                elif isinstance(value, datetime):
                    cleaned_row[key] = value.isoformat()
                else:
                    cleaned_row[key] = str(value)
            writer.writerow(cleaned_row)

        return output.getvalue()

    @staticmethod
    def to_json(data: Any, indent: int = 2) -> str:
        """
        Convert data to JSON string

        Args:
            data: Data to export (dict, list, etc.)
            indent: JSON indentation level

        Returns:
            JSON string
        """

        def json_serializer(obj):
            """Custom JSON serializer for datetime and other types"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(
            data, indent=indent, default=json_serializer, ensure_ascii=False
        )

    @staticmethod
    def export_students_to_csv(students: List[Dict]) -> str:
        """Export student data to CSV"""
        fieldnames = [
            "student_id",
            "email",
            "total_sessions",
            "total_practice",
            "total_qa",
            "active_goals",
            "level",
            "total_xp",
            "badges_count",
            "current_streak",
            "last_activity",
        ]
        return DataExporter.to_csv(students, fieldnames)

    @staticmethod
    def export_overrides_to_csv(overrides: List[Dict]) -> str:
        """Export override data to CSV"""
        fieldnames = [
            "override_id",
            "tutor_id",
            "student_id",
            "override_type",
            "subject",
            "difficulty_level",
            "reason",
            "created_at",
        ]
        return DataExporter.to_csv(overrides, fieldnames)

    @staticmethod
    def export_analytics_to_json(analytics: Dict) -> str:
        """Export analytics data to JSON"""
        return DataExporter.to_json(analytics)
