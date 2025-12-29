from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    # Portfolio management (authenticated)
    path('', views.PortfolioView.as_view(), name='portfolio'),
    
    # Portfolio items
    path('items/', views.PortfolioItemListView.as_view(), name='portfolio_items'),
    path('items/<int:item_id>/', views.PortfolioItemDetailView.as_view(), name='portfolio_item_detail'),
    path('items/reorder/', views.PortfolioItemReorderView.as_view(), name='portfolio_items_reorder'),
    
    # Project data for wizard
    path('project-from-token/<str:share_token>/', views.project_from_token, name='project_from_token'),
    
    # Public portfolio views
    path('public/<str:username>/', views.public_portfolio_by_username, name='public_portfolio_username'),
    path('public/custom/<str:custom_url>/', views.public_portfolio_by_custom_url, name='public_portfolio_custom'),
]

