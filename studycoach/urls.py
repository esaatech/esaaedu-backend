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
        "sessions/<uuid:session_id>/extend/",
        views.StudySessionExtendView.as_view(),
        name="studycoach-session-extend",
    ),
    path(
        "sessions/<uuid:session_id>/answer/",
        views.StudySessionAnswerView.as_view(),
        name="studycoach-session-answer",
    ),
    path(
        "sessions/<uuid:session_id>/grade/",
        views.StudySessionGradeView.as_view(),
        name="studycoach-session-grade",
    ),
    path(
        "memories/",
        views.CoachMemoryListView.as_view(),
        name="studycoach-memories",
    ),
    path(
        "memories/<uuid:lesson_id>/reread/",
        views.CoachMemoryRereadView.as_view(),
        name="studycoach-memory-reread",
    ),
    path(
        "lesson-bank/<uuid:lesson_id>/",
        views.LessonCoachBankView.as_view(),
        name="studycoach-lesson-bank",
    ),
    path(
        "lesson-bank/<uuid:lesson_id>/catalog/",
        views.LessonCoachCatalogView.as_view(),
        name="studycoach-lesson-catalog",
    ),
    path(
        "lesson-bank/<uuid:lesson_id>/generate/",
        views.LessonCoachGenerateView.as_view(),
        name="studycoach-lesson-generate",
    ),
    path(
        "lesson-bank/<uuid:lesson_id>/items/",
        views.LessonCoachItemListCreateView.as_view(),
        name="studycoach-lesson-items",
    ),
    path(
        "coach-items/<uuid:item_id>/",
        views.CoachItemDetailView.as_view(),
        name="studycoach-item-detail",
    ),
]
