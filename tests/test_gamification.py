"""
Gamification Tests
Tests for XP, levels, badges, streaks, and leaderboards
"""

import pytest
import uuid
from datetime import datetime, timedelta

pytest.importorskip("src.services.gamification", reason="gamification feature was never implemented")

from src.services.gamification.engine import GamificationEngine
from src.services.gamification.badges import BadgeSystem
from tests.test_models import TestUser, TestPracticeAssignment, TestGoal, TestQAInteraction, TestSession, TestSubject
from sqlalchemy.orm import Session


def test_award_xp_basic(db_session: Session):
    """Test basic XP awarding"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.award_xp(str(user.id), "practice_completed")
    
    assert result["xp_awarded"] == 10
    assert result["total_xp"] == 10
    assert result["level"] == 1
    assert result["level_up"] == False


def test_award_xp_level_up(db_session: Session):
    """Test XP awarding that causes level up"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={"total_xp_earned": 90, "level": 1}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.award_xp(str(user.id), "practice_completed")
    
    # Should level up from 1 to 2 (90 + 10 = 100, which is level 2)
    assert result["level"] == 2
    assert result["level_up"] == True
    assert result["total_xp_earned"] == 100


def test_calculate_level(db_session: Session):
    """Test level calculation"""
    engine = GamificationEngine(db_session)
    
    assert engine.calculate_level(0) == 1
    assert engine.calculate_level(99) == 1
    assert engine.calculate_level(100) == 2
    assert engine.calculate_level(249) == 2
    assert engine.calculate_level(250) == 3


def test_get_xp_for_next_level(db_session: Session):
    """Test getting XP required for next level"""
    engine = GamificationEngine(db_session)
    
    info = engine.get_xp_for_next_level(1)
    assert info["current_level"] == 1
    assert info["next_level"] == 2
    assert info["xp_for_next_level"] == 100
    
    info = engine.get_xp_for_next_level(2)
    assert info["current_level"] == 2
    assert info["next_level"] == 3
    assert info["xp_for_next_level"] == 150  # 100 * 1.5


def test_update_streak_new(db_session: Session):
    """Test streak update for new user"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.update_streak(str(user.id))
    
    assert result["current_streak"] == 1
    assert result["longest_streak"] == 1


def test_update_streak_consecutive(db_session: Session):
    """Test streak update for consecutive days"""
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={
            "streaks": {
                "current_streak": 5,
                "longest_streak": 5,
                "last_activity_date": yesterday.isoformat()
            }
        }
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.update_streak(str(user.id))
    
    assert result["current_streak"] == 6
    assert result["longest_streak"] == 6


def test_update_streak_broken(db_session: Session):
    """Test streak reset when broken"""
    today = datetime.utcnow().date()
    three_days_ago = today - timedelta(days=3)
    
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={
            "streaks": {
                "current_streak": 5,
                "longest_streak": 5,
                "last_activity_date": three_days_ago.isoformat()
            }
        }
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.update_streak(str(user.id))
    
    assert result["current_streak"] == 1
    assert result["longest_streak"] == 5  # Longest streak preserved


def test_streak_weekly_bonus(db_session: Session):
    """Test weekly streak bonus"""
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={
            "streaks": {
                "current_streak": 6,  # Day 6, will become 7
                "longest_streak": 6,
                "last_activity_date": yesterday.isoformat()
            }
        }
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.update_streak(str(user.id))
    
    assert result["current_streak"] == 7
    assert result["streak_bonus_xp"] == 50  # Weekly bonus


def test_badge_award(db_session: Session):
    """Test badge awarding"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    badge_system = BadgeSystem(db_session)
    awarded = badge_system.award_badge(str(user.id), "level_5")
    
    assert awarded == True
    
    badges = badge_system.get_user_badges(str(user.id))
    assert len(badges) == 1
    assert badges[0]["id"] == "level_5"


def test_badge_duplicate(db_session: Session):
    """Test that duplicate badges aren't awarded"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={"badges": ["level_5"]}
    )
    db_session.add(user)
    db_session.commit()
    
    badge_system = BadgeSystem(db_session)
    awarded = badge_system.award_badge(str(user.id), "level_5")
    
    assert awarded == False  # Already has badge
    
    badges = badge_system.get_user_badges(str(user.id))
    assert len(badges) == 1


def test_level_badge_check(db_session: Session):
    """Test level-based badge checking"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    badge_system = BadgeSystem(db_session)
    badges = badge_system.check_level_badges(str(user.id), 5)
    
    assert "level_5" in badges
    
    badges = badge_system.check_level_badges(str(user.id), 10)
    assert "level_10" in badges


def test_practice_badge_check(db_session: Session):
    """Test practice-based badge checking"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    subject = TestSubject(
        id=str(uuid.uuid4()),
        name="Math",
        category="Math"
    )
    db_session.add_all([user, subject])
    db_session.commit()
    
    # Create 10 completed practice assignments
    for i in range(10):
        practice = TestPracticeAssignment(
            id=str(uuid.uuid4()),
            student_id=user.id,
            source="bank",
            completed=True,
            subject_id=subject.id
        )
        db_session.add(practice)
    db_session.commit()
    
    badge_system = BadgeSystem(db_session)
    badges = badge_system.check_action_badges(
        str(user.id),
        "practice_completed",
        {"perfect_score": False}
    )
    
    assert "practice_10" in badges


def test_leaderboard(db_session: Session):
    """Test leaderboard generation"""
    # Create multiple users with different XP
    users = []
    for i in range(5):
        user = TestUser(
            id=str(uuid.uuid4()),
            cognito_sub=f"test-sub-{i}",
            email=f"test{i}@test.com",
            role="student",
            gamification={
                "total_xp_earned": (5 - i) * 100,  # Decreasing XP
                "level": (5 - i)
            }
        )
        users.append(user)
        db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    leaderboard = engine.get_leaderboard(limit=5)
    
    assert len(leaderboard) == 5
    # Should be sorted by XP descending
    assert leaderboard[0]["total_xp"] == 500
    assert leaderboard[4]["total_xp"] == 100


def test_get_user_gamification(db_session: Session):
    """Test getting user gamification state"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={
            "xp": 50,
            "level": 1,
            "badges": ["level_5"],
            "streaks": {"current_streak": 3},
            "total_xp_earned": 50
        }
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    gamification = engine.get_user_gamification(str(user.id))
    
    assert gamification["xp"] == 50
    assert gamification["level"] == 1
    assert len(gamification["badges"]) == 1
    assert gamification["streaks"]["current_streak"] == 3


def test_practice_perfect_xp(db_session: Session):
    """Test perfect practice score awards bonus XP"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    
    # Regular practice completion
    result1 = engine.award_xp(str(user.id), "practice_completed")
    assert result1["xp_awarded"] == 10
    
    # Perfect practice completion
    result2 = engine.award_xp(str(user.id), "practice_perfect")
    assert result2["xp_awarded"] == 25


def test_session_completion_xp(db_session: Session):
    """Test session completion awards XP"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.award_xp(str(user.id), "session_completed")
    
    assert result["xp_awarded"] == 50


def test_goal_creation_xp(db_session: Session):
    """Test goal creation awards XP"""
    user = TestUser(
        id=str(uuid.uuid4()),
        cognito_sub="test-sub",
        email="test@test.com",
        role="student",
        gamification={}
    )
    db_session.add(user)
    db_session.commit()
    
    engine = GamificationEngine(db_session)
    result = engine.award_xp(str(user.id), "goal_created")
    
    assert result["xp_awarded"] == 20

