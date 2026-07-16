"""
Tests for configurable CORS origins (Phase 5, task 5.2).
Verifies parse_allowed_origins() semantics and that the default ("*")
config preserves today's permissive CORS behavior on the live app.
"""

from src.api.main import parse_allowed_origins


def test_parse_allowed_origins_wildcard():
    """ "*" means allow all, returned as-is."""
    assert parse_allowed_origins("*") == ["*"]


def test_parse_allowed_origins_single_origin():
    assert parse_allowed_origins("http://allowed.example") == ["http://allowed.example"]


def test_parse_allowed_origins_multiple_with_spaces():
    value = "http://a.example, http://b.example ,http://c.example"
    assert parse_allowed_origins(value) == [
        "http://a.example",
        "http://b.example",
        "http://c.example",
    ]


def test_parse_allowed_origins_empty_string_defaults_to_wildcard():
    """Empty/unset value falls back to the permissive default."""
    assert parse_allowed_origins("") == ["*"]


def test_parse_allowed_origins_whitespace_only_defaults_to_wildcard():
    assert parse_allowed_origins("   ") == ["*"]


def test_cors_preflight_default_allows_all_origins(client):
    """With the default ALLOWED_ORIGINS=* config, a CORS preflight request
    from any origin should succeed, matching current behavior."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://any-origin.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    # Starlette's CORSMiddleware reflects the requesting origin (rather than
    # literal "*") whenever allow_credentials=True, per the CORS spec. This
    # matches today's behavior before this change.
    assert (
        response.headers["access-control-allow-origin"] == "http://any-origin.example"
    )
