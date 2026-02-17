from rest_framework import serializers
from .models import Post


class PostAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)


class PostListSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'excerpt', 'published_at', 'author']

    def get_excerpt(self, obj):
        if not obj.content:
            return ''
        max_length = 160
        if len(obj.content) <= max_length:
            return obj.content
        return obj.content[:max_length].rsplit(' ', 1)[0] + '…'


class PostDetailSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'content', 'author', 'published_at', 'created_at', 'updated_at']


class PostCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a post (e.g. from book export)."""

    class Meta:
        model = Post
        fields = ['title', 'content']
        extra_kwargs = {'title': {'required': True}, 'content': {'required': True}}

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        if not user:
            raise serializers.ValidationError('Authentication required')
        return Post.objects.create(
            author=user,
            status=Post.Status.DRAFT,
            **validated_data,
        )
