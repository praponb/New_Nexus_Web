"""WebSocket auth: `?token=<jwt access token>` → scope["user"]."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_for_token(raw: str):
    try:
        token = AccessToken(raw)
        user_id = token[api_settings.USER_ID_CLAIM]
    except (TokenError, KeyError):
        return AnonymousUser()
    User = get_user_model()
    try:
        user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
    except User.DoesNotExist:
        return AnonymousUser()
    return user if user.is_active else AnonymousUser()


class JWTQueryAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        token = (params.get("token") or [""])[0]
        scope = dict(scope, user=await _user_for_token(token) if token else AnonymousUser())
        return await super().__call__(scope, receive, send)
