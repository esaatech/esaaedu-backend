from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView, ListCreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import BlogCategory, Post
from .serializers import (
    BlogCategorySerializer,
    BlogCategoryCreateSerializer,
    PostListSerializer,
    PostDetailSerializer,
    PostCreateSerializer,
    PostMyListSerializer,
    PostUpdateSerializer,
)


def _posts_with_categories():
    return Post.objects.prefetch_related('categories')


class PostListView(ListAPIView):
    """
    List published blog posts.
    GET /api/blog/?category=<slug>
    """
    permission_classes = [AllowAny]
    serializer_class = PostListSerializer

    def get_queryset(self):
        queryset = _posts_with_categories().filter(
            status=Post.Status.PUBLISHED,
        ).order_by('-published_at')
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(categories__slug__iexact=category_slug).distinct()
        return queryset


class PostDetailView(RetrieveAPIView):
    """
    Retrieve a single published post by slug.
    GET /api/blog/<slug>/
    """
    permission_classes = [AllowAny]
    serializer_class = PostDetailSerializer
    lookup_url_kwarg = 'slug'
    lookup_field = 'slug'

    def get_queryset(self):
        return _posts_with_categories().filter(status=Post.Status.PUBLISHED)


class PostCreateView(CreateAPIView):
    """
    Create a draft blog post (e.g. from book export).
    POST /api/blog/create/
    Requires authentication.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PostCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance = _posts_with_categories().get(pk=instance.pk)
        return Response(
            PostDetailSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class MyPostListView(ListAPIView):
    """
    List current user's blog posts (draft and published).
    GET /api/blog/mine/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PostMyListSerializer

    def get_queryset(self):
        return _posts_with_categories().filter(
            author=self.request.user,
        ).order_by('-updated_at')


class MyPostDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a post owned by the current user.
    GET /api/blog/mine/<id>/
    PATCH /api/blog/mine/<id>/  (sets status to draft)
    DELETE /api/blog/mine/<id>/
    """
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'pk'
    lookup_field = 'pk'

    def get_queryset(self):
        return _posts_with_categories().filter(author=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return PostUpdateSerializer
        return PostDetailSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.status = Post.Status.DRAFT
        instance.save(update_fields=['status', 'updated_at'])

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = _posts_with_categories().get(pk=instance.pk)
        return Response(PostDetailSerializer(instance).data)


class BlogCategoryListCreateView(ListCreateAPIView):
    """
    List all blog categories or create a new one.
    GET /api/blog/categories/
    POST /api/blog/categories/  (authenticated teachers)
    """
    queryset = BlogCategory.objects.all().order_by('name')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BlogCategoryCreateSerializer
        return BlogCategorySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            BlogCategorySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )
