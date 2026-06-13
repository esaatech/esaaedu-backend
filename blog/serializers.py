from rest_framework import serializers
from .models import BlogCategory, Post


class PostAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)


class BlogCategorySerializer(serializers.ModelSerializer):
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug', 'post_count']

    def get_post_count(self, obj):
        return obj.posts.filter(status=Post.Status.PUBLISHED).count()


class BlogCategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ['name']

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Category name is required.')
        if BlogCategory.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return name


def _set_post_categories(post, category_ids):
    if category_ids is None:
        return
    categories = BlogCategory.objects.filter(id__in=category_ids)
    if len(category_ids) != categories.count():
        raise serializers.ValidationError({'category_ids': 'One or more category IDs are invalid.'})
    post.categories.set(categories)


class PostListSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    excerpt = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'excerpt', 'published_at', 'author', 'categories']

    def get_excerpt(self, obj):
        if not obj.content:
            return ''
        max_length = 160
        if len(obj.content) <= max_length:
            return obj.content
        return obj.content[:max_length].rsplit(' ', 1)[0] + '…'


class PostDetailSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    categories = BlogCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'author', 'published_at',
            'created_at', 'updated_at', 'categories',
        ]


class PostCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a post (e.g. from book export)."""
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Post
        fields = ['title', 'content', 'category_ids']
        extra_kwargs = {'title': {'required': True}, 'content': {'required': True}}

    def create(self, validated_data):
        category_ids = validated_data.pop('category_ids', None)
        request = self.context.get('request')
        user = request.user if request else None
        if not user:
            raise serializers.ValidationError('Authentication required')
        post = Post.objects.create(
            author=user,
            status=Post.Status.DRAFT,
            **validated_data,
        )
        _set_post_categories(post, category_ids)
        return post


class PostMyListSerializer(serializers.ModelSerializer):
    """List serializer for current user's posts (includes status)."""
    author = PostAuthorSerializer(read_only=True)
    excerpt = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'status', 'published_at',
            'updated_at', 'author', 'categories',
        ]

    def get_excerpt(self, obj):
        if not obj.content:
            return ''
        max_length = 160
        if len(obj.content) <= max_length:
            return obj.content
        return obj.content[:max_length].rsplit(' ', 1)[0] + '…'


class PostUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for updating a post."""
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Post
        fields = ['title', 'content', 'category_ids']
        extra_kwargs = {'title': {'required': False}, 'content': {'required': False}}

    def update(self, instance, validated_data):
        category_ids = validated_data.pop('category_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        _set_post_categories(instance, category_ids)
        return instance
