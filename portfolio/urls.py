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
    
    # Public portfolio (path segment matches User.public_handle)
    path('public/<str:public_handle>/', views.public_portfolio_by_public_handle, name='public_portfolio'),
]

