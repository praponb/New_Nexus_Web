import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

PASSWORD = "Sup3r-Secure-Pass!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(email=None, password=PASSWORD, **extra):
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.com"
        return User.objects.create_user(email=email, password=password, **extra)

    return _make


@pytest.fixture
def user(make_user):
    return make_user(email="alex@example.com", full_name="Alex Taylor")


@pytest.fixture
def auth_client(user):
    from apps.accounts.serializers import tokens_for

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_for(user)['access']}")
    return client
