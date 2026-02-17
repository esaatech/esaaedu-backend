from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Post
from .serializers import (
    PostListSerializer,
    PostDetailSerializer,
    PostCreateSerializer,
    PostMyListSerializer,
    PostUpdateSerializer,
)


class PostListView(ListAPIView):
    """
    List published blog posts.
    GET /api/blog/
    """
    permission_classes = [AllowAny]
    serializer_class = PostListSerializer
    queryset = Post.objects.filter(status=Post.Status.PUBLISHED).order_by('-published_at')


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
        return Post.objects.filter(status=Post.Status.PUBLISHED)


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
        return Post.objects.filter(author=self.request.user).order_by('-updated_at')


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
        return Post.objects.filter(author=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return PostUpdateSerializer
        return PostDetailSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.status = Post.Status.DRAFT
        instance.save(update_fields=['status', 'updated_at'])
