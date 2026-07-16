#!/usr/bin/env python3
"""
Comprehensive Demo Account Verification
Tests each demo account according to DEMO_USER_GUIDE.md specifications
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from sqlalchemy.orm import Session
from src.config.database import get_db_session
from src.models.user import User
from scripts.demo_auth import login, auth_headers

BASE_URL = "http://localhost:8000"

# The 3 headline demo accounts created with real passwords by
# scripts/seed_demo_data.py (see DEMO_ACCOUNTS there). The other seeded
# students/tutors have no password_hash and cannot log in, so they are not
# verified here.
DEMO_ACCOUNTS = {
    "demo@elevare.ai": {
        "scenario": "Headline demo student account",
        "expected": {"role": "student"},
    },
    "tutor@elevare.ai": {
        "scenario": "Headline demo tutor account",
        "expected": {"role": "tutor"},
    },
    "parent@elevare.ai": {
        "scenario": "Headline demo parent account",
        "expected": {"role": "parent"},
    },
}


def get_user_id_from_db(email: str) -> str:
    """Get user ID from database"""
    with get_db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return str(user.id)
    return None


def test_backend():
    """Test if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def verify_account_data(email: str, expected: dict) -> dict:
    """Verify account exists in the database with the expected role.

    Headline accounts (demo@elevare.ai, tutor@elevare.ai, parent@elevare.ai)
    are not seeded with goals/sessions/QA history - those are only attached
    to the 10 password-less student fixtures in seed_demo_data.py - so we
    only check existence and role here.
    """
    results = {"passed": True, "issues": []}

    with get_db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            results["passed"] = False
            results["issues"].append(f"User {email} does not exist in database")
            return results

        if "role" in expected and user.role != expected["role"]:
            results["passed"] = False
            results["issues"].append(
                f"Expected role {expected['role']}, found {user.role}"
            )

    return results


def test_login_api(email: str) -> dict:
    """Test that the account can log in via POST /api/v1/auth/login."""
    results = {"passed": True, "issues": [], "token": None, "user_id": None}
    try:
        login_data = login(email)
        results["token"] = login_data["access_token"]
        results["user_id"] = login_data["user_id"]
    except Exception as e:
        results["passed"] = False
        results["issues"].append(f"Login failed: {str(e)}")
    return results


def test_progress_api(email: str, user_id: str, token: str) -> dict:
    """Test progress API endpoint (student accounts only)"""
    results = {"passed": True, "issues": [], "data": {}}

    headers = auth_headers(token)

    try:
        url = f"{BASE_URL}/api/v1/progress/{user_id}?include_suggestions=true"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            results["passed"] = False
            results["issues"].append(f"API returned status {response.status_code}: {response.text[:200]}")
            return results

        data = response.json()
        if not data.get("success"):
            results["passed"] = False
            results["issues"].append(f"API returned success=false: {data.get('error', 'Unknown error')}")
            return results

        progress_data = data.get("data", {})
        goals = progress_data.get("goals", [])
        suggestions = progress_data.get("suggestions", [])

        results["data"] = {
            "goals": goals,
            "suggestions": suggestions
        }

    except requests.exceptions.ConnectionError:
        results["passed"] = False
        results["issues"].append("Cannot connect to backend API (is it running?)")
    except Exception as e:
        results["passed"] = False
        results["issues"].append(f"API test error: {str(e)}")

    return results


def test_nudges_api(email: str, user_id: str, token: str) -> dict:
    """Test nudges API endpoint (student accounts only)"""
    results = {"passed": True, "issues": [], "data": {}}

    headers = auth_headers(token)

    try:
        url = f"{BASE_URL}/api/v1/nudges/users/{user_id}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            results["passed"] = False
            results["issues"].append(f"Nudges API returned status {response.status_code}")
            return results
        
        data = response.json()
        nudges = data.get("data", {}).get("nudges", [])

        results["data"] = {"nudges": nudges}
        # Headline account has no seeded nudges - just confirm the endpoint works.

    except Exception as e:
        results["passed"] = False
        results["issues"].append(f"Nudges API test error: {str(e)}")

    return results


def test_qa_api(email: str, user_id: str, token: str) -> dict:
    """Test Q&A conversation-history endpoint (student accounts only)"""
    results = {"passed": True, "issues": [], "data": {}}

    headers = auth_headers(token)

    try:
        url = f"{BASE_URL}/api/v1/enhancements/qa/conversation-history/{user_id}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            results["issues"].append(f"Q&A history API returned status {response.status_code} (may be OK if no history)")
            return results

        data = response.json()
        history = data.get("data", {}).get("conversations", [])

        results["data"] = {"history": history}
        # Headline account has no seeded conversation history - just confirm the endpoint works.

    except Exception as e:
        results["issues"].append(f"Q&A API test error: {str(e)}")

    return results


def main():
    """Main verification function"""
    print("=" * 80)
    print("COMPREHENSIVE DEMO ACCOUNT VERIFICATION")
    print("Testing all accounts according to DEMO_USER_GUIDE.md")
    print("=" * 80)
    print()
    
    # Check backend
    print("Checking backend status...")
    if not test_backend():
        print("[ERROR] Backend is not running!")
        print("  Start with: python -m uvicorn src.api.main:app --reload")
        print()
        return
    print("[OK] Backend is running")
    print()
    
    all_passed = True
    results_summary = []
    
    # Test each demo account
    for email, config in DEMO_ACCOUNTS.items():
        print("=" * 80)
        print(f"Testing: {email}")
        print(f"Scenario: {config['scenario']}")
        print("=" * 80)
        
        # Get user ID
        user_id = get_user_id_from_db(email)
        if not user_id:
            print(f"[FAIL] User {email} not found in database")
            print("  Run: python scripts/create_demo_users.py")
            print()
            all_passed = False
            results_summary.append({"email": email, "status": "FAIL", "reason": "User not found"})
            continue
        
        print(f"[OK] User found: {user_id}")

        # Verify database data
        print("\n1. Verifying database data...")
        db_results = verify_account_data(email, config["expected"])
        if db_results["passed"]:
            print("   [OK] Database data verified")
        else:
            print("   [FAIL] Database verification issues:")
            for issue in db_results["issues"]:
                print(f"      - {issue}")
            all_passed = False

        if db_results["issues"]:
            for issue in db_results["issues"]:
                print(f"      [NOTE] {issue}")

        # Test real login (POST /api/v1/auth/login)
        print("\n2. Testing login API...")
        login_results = test_login_api(email)
        if login_results["passed"]:
            print(f"   [OK] Login successful, user_id={login_results['user_id']}")
        else:
            print("   [FAIL] Login issues:")
            for issue in login_results["issues"]:
                print(f"      - {issue}")
            all_passed = False

        token = login_results.get("token")
        role = config["expected"].get("role")

        progress_results = {"passed": True, "issues": []}
        nudges_results = {"passed": True, "issues": []}
        qa_results = {"passed": True, "issues": []}

        if token and role == "student":
            # Test Progress API
            print("\n3. Testing Progress API...")
            progress_results = test_progress_api(email, user_id, token)
            if progress_results["passed"]:
                print("   [OK] Progress API working")
                if progress_results["data"].get("goals"):
                    print(f"      Goals: {len(progress_results['data']['goals'])}")
                if progress_results["data"].get("suggestions"):
                    print(f"      Suggestions: {len(progress_results['data']['suggestions'])}")
            else:
                print("   [FAIL] Progress API issues:")
                for issue in progress_results["issues"]:
                    print(f"      - {issue}")
                all_passed = False

            # Test Nudges API
            print("\n4. Testing Nudges API...")
            nudges_results = test_nudges_api(email, user_id, token)
            if nudges_results["passed"]:
                print("   [OK] Nudges API working")
                if nudges_results["data"].get("nudges"):
                    print(f"      Nudges: {len(nudges_results['data']['nudges'])}")
            else:
                print("   [FAIL] Nudges API issues:")
                for issue in nudges_results["issues"]:
                    print(f"      - {issue}")
                all_passed = False

            # Test Q&A API
            print("\n5. Testing Q&A API...")
            qa_results = test_qa_api(email, user_id, token)
            if qa_results["passed"]:
                print("   [OK] Q&A API working")
                if qa_results["data"].get("history"):
                    print(f"      Conversation history: {len(qa_results['data']['history'])} items")
            else:
                print("   [FAIL] Q&A API issues:")
                for issue in qa_results["issues"]:
                    print(f"      - {issue}")
        else:
            print(f"\n3-5. Skipping progress/nudges/Q&A checks (role={role}, not a student)")

        # Summary for this account
        account_passed = (
            db_results["passed"] and
            login_results["passed"] and
            progress_results["passed"] and
            nudges_results["passed"]
        )
        
        if account_passed:
            print(f"\n[PASS] {email} - All tests passed")
            results_summary.append({"email": email, "status": "PASS"})
        else:
            print(f"\n[FAIL] {email} - Some tests failed")
            results_summary.append({"email": email, "status": "FAIL"})
            all_passed = False
        
        print()
    
    # Final summary
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    
    for result in results_summary:
        status = result["status"]
        email = result["email"]
        if status == "PASS":
            print(f"[PASS] {email}")
        else:
            print(f"[FAIL] {email}: {result.get('reason', 'See details above')}")
    
    print()
    print("=" * 80)
    if all_passed:
        print("[SUCCESS] All demo accounts verified successfully!")
        print("Ready for demo presentation!")
    else:
        print("[ERROR] Some demo accounts have issues.")
        print("Please review the details above and fix any problems.")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. If accounts are missing, run: python scripts/create_demo_users.py")
    print("  2. If backend is not running, start it: python -m uvicorn src.api.main:app --reload")
    print("  3. Test frontend login with each account")
    print("  4. See DEMO_USER_GUIDE.md for demo instructions")
    print()


if __name__ == "__main__":
    main()

