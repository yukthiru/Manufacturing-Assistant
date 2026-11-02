from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("machines", views.MachineViewSet, basename="machine")
router.register("manuals", views.ManualViewSet, basename="manual")
router.register("questions", views.QuestionViewSet, basename="question")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("ask/", views.AskView.as_view()),
    path("", include(router.urls)),
]
