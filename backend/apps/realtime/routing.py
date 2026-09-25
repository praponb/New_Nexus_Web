from django.urls import re_path

from .consumers import ProjectLogConsumer

websocket_urlpatterns = [
    re_path(r"^ws/projects/(?P<project_id>[0-9a-fA-F-]{36})/logs/?$", ProjectLogConsumer.as_asgi()),
]
