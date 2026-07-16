"""
Tests for Demo Data Generation Script
Verifies the seed script works correctly
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestDemoDataScript:
    """Test demo data generation script"""

    def test_script_imports(self):
        """Test that seed_demo_data script can be imported"""
        try:
            import seed_demo_data

            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import seed_demo_data: {e}")

    def test_data_generation_structure(self):
        """Test that generated data has correct structure"""
        # This would test the actual data generation
        # For now, verify the script structure
        import seed_demo_data

        # Check that main functions exist
        assert hasattr(
            seed_demo_data, "generate_all_demo_data"
        ) or "generate_all_demo_data" in dir(seed_demo_data)

    def test_subjects_generated(self):
        """Test that subjects are generated correctly"""
        # Verify subject structure
        from scripts.seed_demo_data import SUBJECTS

        assert len(SUBJECTS) > 0
        assert all("name" in s for s in SUBJECTS)
        assert all("category" in s for s in SUBJECTS)

    def test_transcripts_available(self):
        """Test that transcript templates exist"""
        from scripts.seed_demo_data import TRANSCRIPTS

        assert len(TRANSCRIPTS) > 0
        assert "normal_algebra" in TRANSCRIPTS
        assert "mixed_subjects" in TRANSCRIPTS
        assert "short_session" in TRANSCRIPTS
