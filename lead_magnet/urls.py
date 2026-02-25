"""
URL configuration for lead_magnet app.
"""
from django.urls import path
from . import views

app_name = "lead_magnet"

urlpatterns = [
    path("<slug:slug>/", views.LeadMagnetDetailView.as_view(), name="detail"),
    path("<slug:slug>/submit/", views.LeadMagnetSubmitView.as_view(), name="submit"),
]
