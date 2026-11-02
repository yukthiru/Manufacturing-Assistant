import logging

from django.contrib.auth import authenticate, login, logout
from django.http import FileResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Machine, Manual, Question
from .permissions import CanViewQueryHistory, IsAdministrator, IsEngineer
from .roles import ADMIN, ENGINEER, SUPERVISOR, role_of
from .serializers import (AskSerializer, MachineSerializer, ManualSerializer, QuestionSerializer)

log = logging.getLogger(__name__)


def me_payload(user):
    return {"id": user.id, "username": user.username, "role": role_of(user)}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(me_payload(request.user))


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = authenticate(request, username=request.data.get("username", ""),
                            password=request.data.get("password", ""))
        if user is None:
            return Response({"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(me_payload(user))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MachineViewSet(viewsets.ModelViewSet):
    """Everyone signed in can read; only Administrators can change."""
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdministrator()]


class ManualViewSet(viewsets.ModelViewSet):
    queryset = Manual.objects.select_related("machine", "uploaded_by")
    serializer_class = ManualSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "file"):
            return [IsAuthenticated()]
        return [IsAdministrator()]

    def get_queryset(self):
        qs = super().get_queryset()
        machine = self.request.query_params.get("machine")
        return qs.filter(machine_id=machine) if machine else qs

    def perform_create(self, serializer):
        from . import rag

        manual = serializer.save(uploaded_by=self.request.user)
        try:
            rag.ingest_manual(manual)
        except Exception as exc:
            log.exception("Manual ingestion failed")
            manual.file.delete(save=False)
            manual.delete()
            raise ValidationError({"file": [str(exc)]})

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        manual = self.get_object()
        return FileResponse(manual.file.open("rb"), content_type="application/pdf")


class AskView(APIView):
    permission_classes = [IsEngineer]

    def post(self, request):
        from . import rag

        s = AskSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        machine, text = s.validated_data["machine"], s.validated_data["question"].strip()
        try:
            result = rag.answer_question(machine, text)
        except Exception:
            log.exception("RAG pipeline failed")
            return Response({"detail": "The AI service failed. Please try again."},
                            status=status.HTTP_502_BAD_GATEWAY)
        q = Question.objects.create(user=request.user, machine=machine, text=text, **result)
        return Response(QuestionSerializer(q).data, status=status.HTTP_201_CREATED)


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """Engineers see their own history; Supervisors/Administrators see everyone's (read-only)."""
    serializer_class = QuestionSerializer
    permission_classes = [CanViewQueryHistory]

    def get_queryset(self):
        qs = Question.objects.select_related("machine", "user")
        role = role_of(self.request.user)
        if role == ENGINEER:
            qs = qs.filter(user=self.request.user)
        elif role not in (ADMIN, SUPERVISOR):
            return qs.none()
        p = self.request.query_params
        if p.get("unanswered") in ("1", "true"):
            qs = qs.filter(answered=False)
        if p.get("machine"):
            qs = qs.filter(machine_id=p["machine"])
        return qs
