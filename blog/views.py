from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from .models import Post
from .serializers import PostListSerializer, PostDetailSerializer


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
