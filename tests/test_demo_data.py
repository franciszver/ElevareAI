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
        """Test that the script exposes the idempotent seeding API it now
        uses to write directly to Postgres (deterministic IDs + get_or_create),
        replacing the old in-memory generate_all_demo_data() approach."""
        import seed_demo_data

        assert hasattr(seed_demo_data, "deterministic_id")
        assert hasattr(seed_demo_data, "get_or_create")
        assert hasattr(seed_demo_data, "main")

        # Same natural key -> same UUID (idempotency requirement)
        id_a = seed_demo_data.deterministic_id("user", "demo@elevare.ai")
        id_b = seed_demo_data.deterministic_id("user", "demo@elevare.ai")
        assert id_a == id_b

        # Different natural key -> different UUID
        id_c = seed_demo_data.deterministic_id("user", "someone-else@elevare.ai")
        assert id_a != id_c

    def test_demo_accounts_defined(self):
        """Test that the 3 headline demo accounts are defined with email/role/name"""
        from scripts.seed_demo_data import DEMO_ACCOUNTS

        assert len(DEMO_ACCOUNTS) == 3
        roles = {a["role"] for a in DEMO_ACCOUNTS}
        assert roles == {"student", "tutor", "parent"}
        assert all("email" in a and "name" in a for a in DEMO_ACCOUNTS)

    def test_seed_headline_accounts_requires_demo_password(self, monkeypatch):
        """seed_headline_accounts must refuse to run (before any DB writes) if
        DEMO_PASSWORD isn't configured."""
        import scripts.seed_demo_data as seed_demo_data

        monkeypatch.setattr(seed_demo_data.settings, "demo_password", "")
        with pytest.raises(SystemExit):
            seed_demo_data.seed_headline_accounts(db=None)

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
