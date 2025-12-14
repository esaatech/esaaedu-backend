from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    # Landing page - main endpoint for homepage
    path('', views.LandingPageView.as_view(), name='landing_page'),
    
    # Contact overview - main endpoint for contact page
    path('contact/', views.ContactView.as_view(), name='contact_overview'),
    
    # Individual contact components
    path('contact/methods/', views.ContactMethodView.as_view(), name='contact_methods'),
    path('contact/support-team/', views.SupportTeamView.as_view(), name='support_team'),
    path('contact/faqs/', views.FAQView.as_view(), name='faqs'),
    path('contact/support-hours/', views.SupportHoursView.as_view(), name='support_hours'),
    
    # Contact submissions management (admin only)
    path('contact/submissions/', views.ContactSubmissionView.as_view(), name='contact_submissions'),
    path('contact/submissions/<uuid:submission_id>/', views.ContactSubmissionView.as_view(), name='contact_submission_detail'),
    
    # Assessment form submission (public endpoint)
    path('assessment/', views.AssessmentSubmissionView.as_view(), name='assessment_submission'),
    
    # Course recommendations based on assessment (public endpoint)
    path('assessment/recommendations/', views.CourseRecommendationsView.as_view(), name='course_recommendations'),
    
    # Assessment submissions management (admin only)
    path('assessment/submissions/', views.AssessmentSubmissionListView.as_view(), name='assessment_submissions_list'),
]
