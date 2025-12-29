from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from courses.models import ProjectSubmission
from .models import Portfolio, PortfolioItem
from .serializers import (
    PortfolioSerializer,
    PortfolioItemSerializer,
    PortfolioItemCreateSerializer,
    PublicPortfolioSerializer,
)

User = get_user_model()


class PortfolioView(APIView):
    """
    Get or create student's portfolio
    GET /api/portfolio/ - Get student's portfolio
    POST /api/portfolio/ - Create portfolio
    PUT /api/portfolio/ - Update portfolio
    DELETE /api/portfolio/ - Delete portfolio
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get student's portfolio, create if doesn't exist"""
        portfolio, created = Portfolio.objects.get_or_create(student=request.user)
        serializer = PortfolioSerializer(portfolio, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Create portfolio"""
        # Check if portfolio already exists
        if Portfolio.objects.filter(student=request.user).exists():
            return Response(
                {'error': 'Portfolio already exists. Use PUT to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PortfolioSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            portfolio = serializer.save(student=request.user)
            return Response(
                PortfolioSerializer(portfolio, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Update portfolio"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        serializer = PortfolioSerializer(portfolio, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Delete portfolio"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        portfolio.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortfolioItemListView(APIView):
    """
    List and create portfolio items
    GET /api/portfolio/items/ - List all portfolio items
    POST /api/portfolio/items/ - Add project to portfolio
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all portfolio items for student"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        items = portfolio.items.all()
        serializer = PortfolioItemSerializer(items, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Add project to portfolio"""
        portfolio, created = Portfolio.objects.get_or_create(student=request.user)
        
        serializer = PortfolioItemCreateSerializer(
            data=request.data,
            context={'request': request, 'portfolio': portfolio}
        )
        
        if serializer.is_valid():
            portfolio_item = serializer.save()
            return Response(
                PortfolioItemSerializer(portfolio_item, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PortfolioItemDetailView(APIView):
    """
    Get, update, or delete a portfolio item
    GET /api/portfolio/items/{id}/ - Get portfolio item
    PUT /api/portfolio/items/{id}/ - Update portfolio item
    DELETE /api/portfolio/items/{id}/ - Remove from portfolio
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, item_id):
        """Get portfolio item"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        item = get_object_or_404(PortfolioItem, id=item_id, portfolio=portfolio)
        serializer = PortfolioItemSerializer(item, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, item_id):
        """Update portfolio item"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        item = get_object_or_404(PortfolioItem, id=item_id, portfolio=portfolio)
        serializer = PortfolioItemSerializer(item, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, item_id):
        """Remove item from portfolio"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        item = get_object_or_404(PortfolioItem, id=item_id, portfolio=portfolio)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortfolioItemReorderView(APIView):
    """
    Reorder portfolio items
    POST /api/portfolio/items/reorder/ - Reorder items
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Reorder portfolio items"""
        portfolio = get_object_or_404(Portfolio, student=request.user)
        item_orders = request.data.get('item_orders', [])  # [{id: 1, order: 0}, {id: 2, order: 1}, ...]

        if not isinstance(item_orders, list):
            return Response(
                {'error': 'item_orders must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update order for each item
        for item_order in item_orders:
            item_id = item_order.get('id')
            order = item_order.get('order')
            if item_id and order is not None:
                PortfolioItem.objects.filter(
                    id=item_id,
                    portfolio=portfolio
                ).update(order=order)

        # Return updated items
        items = portfolio.items.all()
        serializer = PortfolioItemSerializer(items, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Public access
def public_portfolio_by_username(request, username):
    """Get public portfolio by username"""
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {'error': 'Portfolio not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    portfolio = get_object_or_404(Portfolio, student=user, is_public=True)
    serializer = PublicPortfolioSerializer(portfolio, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Public access
def public_portfolio_by_custom_url(request, custom_url):
    """Get public portfolio by custom URL"""
    portfolio = get_object_or_404(Portfolio, custom_url=custom_url, is_public=True)
    serializer = PublicPortfolioSerializer(portfolio, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def project_from_token(request, share_token):
    """
    Get project details from share token for portfolio wizard
    GET /api/portfolio/project-from-token/{share_token}/
    """
    try:
        project_submission = ProjectSubmission.objects.get(share_token=share_token)
    except ProjectSubmission.DoesNotExist:
        return Response(
            {'error': 'Invalid share token'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Verify ownership
    if project_submission.student != request.user:
        return Response(
            {'error': 'You can only access your own project submissions'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Use existing serializer
    from courses.serializers import PublicProjectSubmissionSerializer
    serializer = PublicProjectSubmissionSerializer(project_submission, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)
