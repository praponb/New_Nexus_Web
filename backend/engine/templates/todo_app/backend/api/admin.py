from django.contrib import admin

from .models import Todo


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ("title", "completed", "due_date", "created_at")
    list_filter = ("completed",)
    search_fields = ("title", "description")
