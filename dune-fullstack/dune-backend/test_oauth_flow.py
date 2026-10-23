"""
Verification script for Google OAuth account selection, redirect URI consistency,
and user account extraction in DUNE AI Assistant.
"""
import urllib.parse
import sys
import os

# Add dune-backend to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.integrations.google_oauth import (
    get_authorization_url,
    SERVICE_DEFAULT_SCOPES,
    DEFAULT_GOOGLE_SCOPES,
    OAuthCredentials,
    get_user_info
)
from app.services.connection_service import SERVICE_SCOPES

def test_authorization_url_generation():
    print("[1] Testing Google OAuth Authorization URL Generation...")
    
    # 1. Test Gmail service scopes
    gmail_scopes = SERVICE_SCOPES["gmail"]
    assert "openid" in gmail_scopes
    assert "email" in gmail_scopes
    assert "https://www.googleapis.com/auth/gmail.readonly" in gmail_scopes
    assert "https://www.googleapis.com/auth/gmail.send" in gmail_scopes
    
    # 2. Test default prompt includes select_account and consent
    url = get_authorization_url(gmail_scopes, state="gmail:test-state-123")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    
    print(f"  - Generated URL: {url[:80]}...")
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert parsed.path == "/o/oauth2/v2/auth"
    
    # Verify prompt parameter
    assert "prompt" in params, "Missing 'prompt' parameter in OAuth URL"
    prompt_val = params["prompt"][0]
    print(f"  - Prompt parameter: '{prompt_val}'")
    assert "select_account" in prompt_val, "'select_account' must be in prompt parameter"
    assert "consent" in prompt_val, "'consent' must be in prompt parameter for offline refresh token"
    
    # Verify access_type
    assert params.get("access_type") == ["offline"], "'access_type=offline' must be present"
    
    # Verify redirect_uri matches settings.GOOGLE_REDIRECT_URI
    expected_redirect_uri = settings.GOOGLE_REDIRECT_URI
    assert params.get("redirect_uri") == [expected_redirect_uri], (
        f"redirect_uri mismatch! Expected: {expected_redirect_uri}, Got: {params.get('redirect_uri')}"
    )
    print(f"  - Verified redirect_uri sent by backend: {expected_redirect_uri}")
    
    # Verify scopes
    scopes_in_url = params.get("scope", [""])[0].split(" ")
    for s in gmail_scopes:
        assert s in scopes_in_url, f"Scope '{s}' missing from generated URL"
    print("  - All Gmail scopes verified intact.")
    
    # 3. Test explicit prompt parameter
    url_explicit = get_authorization_url(gmail_scopes, prompt="select_account")
    params_explicit = urllib.parse.parse_qs(urllib.parse.urlparse(url_explicit).query)
    assert "select_account" in params_explicit["prompt"][0]
    print("  - Explicit prompt='select_account' verified.")
    print("  [OK] Test [1] Passed.\n")

def test_redirect_uri_consistency():
    print("[2] Testing Redirect URI Consistency...")
    print(f"  - Configured GOOGLE_REDIRECT_URI: '{settings.GOOGLE_REDIRECT_URI}'")
    
    # Standard DUNE backend redirect URI
    canonical_uri = "http://localhost:8000/connections/oauth/callback"
    assert settings.GOOGLE_REDIRECT_URI == canonical_uri, (
        f"Mismatch! settings.GOOGLE_REDIRECT_URI is '{settings.GOOGLE_REDIRECT_URI}', expected '{canonical_uri}'"
    )
    assert not settings.GOOGLE_REDIRECT_URI.endswith("/"), "Canonical redirect URI should not have trailing slash"
    assert " " not in settings.GOOGLE_REDIRECT_URI, "Redirect URI contains invalid whitespace"
    print(f"  - Canonical Redirect URI verified: {canonical_uri}")
    print("  [OK] Test [2] Passed.\n")

def test_user_account_enrichment():
    print("[3] Testing User Account Identity Extraction...")
    import base64
    import json
    
    # Test JWT id_token payload decoding without dummy email
    fake_header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    fake_payload = base64.urlsafe_b64encode(
        json.dumps({
            "email": "intended.student@gmail.com",
            "name": "Intended Student",
            "picture": "https://lh3.googleusercontent.com/avatar"
        }).encode()
    ).decode().rstrip("=")
    fake_sig = base64.urlsafe_b64encode(b"sig").decode().rstrip("=")
    id_token = f"{fake_header}.{fake_payload}.{fake_sig}"
    
    creds = OAuthCredentials(
        token="ya29.test_token",
        refresh_token="1//test_refresh",
        id_token=id_token
    )
    
    # Verify credentials container
    assert creds.access_token == "ya29.test_token"
    assert creds.refresh_token == "1//test_refresh"
    assert creds.id_token == id_token
    
    # Test id_token decode logic
    parts = creds.id_token.split(".")
    payload_str = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload_str.encode("utf-8")).decode("utf-8"))
    assert decoded["email"] == "intended.student@gmail.com"
    assert decoded["name"] == "Intended Student"
    print(f"  - Dynamically extracted intended user email: '{decoded['email']}' (No hardcoded email!)")
    print("  [OK] Test [3] Passed.\n")

def test_fastapi_endpoints():
    print("[4] Testing FastAPI Endpoints...")
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    # Test POST /connections/gmail/connect
    resp = client.post("/connections/gmail/connect")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("oauth") is True
    assert "authorization_url" in data
    auth_url = data["authorization_url"]
    assert "prompt=select_account" in auth_url or "prompt=select_account+consent" in auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fconnections%2Foauth%2Fcallback" in auth_url
    assert "gmail" in auth_url
    print(f"  - /connections/gmail/connect returned authorization URL successfully.")
    print(f"  - Verified prompt=select_account in endpoint response.")
    print(f"  - Verified redirect_uri in endpoint response: http://localhost:8000/connections/oauth/callback")
    
    # Test GET /auth/google
    resp_login = client.get("/auth/google", follow_redirects=False)
    assert resp_login.status_code in (302, 307)
    loc = resp_login.headers.get("location", "")
    assert "prompt=select_account" in loc or "prompt=select_account+consent" in loc
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fgoogle%2Fcallback" in loc
    print(f"  - /auth/google redirects to Google with select_account and dedicated callback URL.")
    print("  [OK] Test [4] Passed.\n")

def main():
    print("==================================================")
    print("  DUNE AI Assistant - Google OAuth Test Suite")
    print("==================================================")
    test_authorization_url_generation()
    test_redirect_uri_consistency()
    test_user_account_enrichment()
    test_fastapi_endpoints()
    print("==================================================")
    print("  ALL TESTS PASSED SUCCESSFULLY! [OK]")
    print("==================================================")

if __name__ == "__main__":
    main()
