from rest_framework import viewsets

from .models import Todo
from .serializers import TodoSerializer


class TodoViewSet(viewsets.ModelViewSet):
    serializer_class = TodoSerializer

    def get_queryset(self):
        queryset = Todo.objects.all()
        status = self.request.query_params.get("status")
        if status == "active":
            queryset = queryset.filter(completed=False)
        elif status == "completed":
            queryset = queryset.filter(completed=True)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset
