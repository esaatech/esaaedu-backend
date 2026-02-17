from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Post
from .serializers import PostListSerializer, PostDetailSerializer, PostCreateSerializer


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
