from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "is_active", "is_staff", "created_at")
    ordering = ("-created_at",)
    search_fields = ("email", "full_name")
    fieldsets = BaseUserAdmin.fieldsets + (("Nexus", {"fields": ("full_name",)}),)
