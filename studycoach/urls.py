from django.urls import path

from . import views

urlpatterns = [
    path("sessions/", views.StudySessionListCreateView.as_view(), name="studycoach-sessions"),
    path(
        "sessions/<uuid:session_id>/",
        views.StudySessionDetailView.as_view(),
        name="studycoach-session-detail",
    ),
    path(
        "sessions/<uuid:session_id>/answer/",
        views.StudySessionAnswerView.as_view(),
        name="studycoach-session-answer",
    ),
]
