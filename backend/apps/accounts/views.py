from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from nexus_backend.api import ApiError, ok

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer, tokens_for


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return ok({"user": UserSerializer(user).data, "tokens": tokens_for(user)}, status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            raise ApiError("Invalid email or password.", code="invalid_credentials", status_code=401)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        return ok({"user": UserSerializer(user).data, "tokens": tokens_for(user)})


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise ApiError(str(exc), code="token_not_valid", status_code=401)
        return ok(serializer.validated_data)


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass
        return ok({"logged_out": True})


class MeView(APIView):
    def get(self, request):
        user = request.user
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from apps.projects.models import GenerationTask, ProjectStatus

        projects = user.projects.all()
        generations_this_month = GenerationTask.objects.filter(
            project__owner=user, created_at__gte=month_start
        ).count()
        limit = int(getattr(settings, "NEXUS_MONTHLY_GENERATION_QUOTA", 25))
        return ok(
            {
                "user": UserSerializer(user).data,
                "quota": {
                    "projects_count": projects.count(),
                    "completed_projects": projects.filter(status=ProjectStatus.COMPLETED).count(),
                    "generations_this_month": generations_this_month,
                    "monthly_generation_limit": limit,
                    "remaining_generations": max(limit - generations_this_month, 0),
                },
            }
        )

    def patch(self, request):
        full_name = request.data.get("full_name")
        if full_name is not None:
            request.user.full_name = str(full_name)[:150]
            request.user.save(update_fields=["full_name", "updated_at"])
        return ok({"user": UserSerializer(request.user).data})
