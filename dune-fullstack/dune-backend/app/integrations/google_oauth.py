from typing import List
from app.core.config import settings

class OAuthCredentials:
    def __init__(self, token: str, refresh_token: str = "mock_refresh_token"):
        self.token = token
        self.refresh_token = refresh_token

def get_authorization_url(scopes: List[str], state: str) -> str:
    """Generates Google OAuth 2.0 authorization URL."""
    scope_str = "%20".join(scopes)
    client_id = settings.GOOGLE_CLIENT_ID or "mock-client-id.apps.googleusercontent.com"
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"scope={scope_str}&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

def exchange_code_for_tokens(code: str, scopes: List[str], state: str) -> OAuthCredentials:
    """Exchanges authorization code for access and refresh tokens."""
    return OAuthCredentials(token=f"mock_google_token_{code[:8]}", refresh_token="mock_refresh_token_xyz")
