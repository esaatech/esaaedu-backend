from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.PostListView.as_view(), name='post_list'),
    path('create/', views.PostCreateView.as_view(), name='post_create'),
    path('mine/', views.MyPostListView.as_view(), name='my_post_list'),
    path('mine/<int:pk>/', views.MyPostDetailView.as_view(), name='my_post_detail'),
    path('<slug:slug>/', views.PostDetailView.as_view(), name='post_detail'),
]
