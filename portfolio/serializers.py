from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Portfolio, PortfolioItem
from courses.models import ProjectSubmission
from courses.serializers import PublicProjectSubmissionSerializer

User = get_user_model()


def _absolute_file_url(request, file_field):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request:
        return request.build_absolute_uri(url)
    return url


class PortfolioItemSerializer(serializers.ModelSerializer):
    """Serializer for portfolio items (student view)"""
    project_submission_id = serializers.PrimaryKeyRelatedField(
        source='project_submission',
        queryset=ProjectSubmission.objects.all(),
        write_only=True
    )
    project_details = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioItem
        fields = [
            'id',
            'portfolio',
            'project_submission_id',
            'project_submission',
            'title',
            'description',
            'featured',
            'order',
            'category',
            'tags',
            'skills_demonstrated',
            'thumbnail_image',
            'demo_url',
            'screenshots',
            'is_visible',
            'created_at',
            'updated_at',
            'project_details',
        ]
        read_only_fields = ['id', 'portfolio', 'project_submission', 'created_at', 'updated_at']

    def get_project_details(self, obj):
        """Get project submission details"""
        if obj.project_submission:
            serializer = PublicProjectSubmissionSerializer(
                obj.project_submission,
                context=self.context
            )
            return serializer.data
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        data["thumbnail_image"] = _absolute_file_url(request, instance.thumbnail_image)
        return data


class PortfolioSerializer(serializers.ModelSerializer):
    """Serializer for portfolio (student view)"""
    items = PortfolioItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_email = serializers.SerializerMethodField()
    resume_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Portfolio
        fields = [
            'id',
            'student',
            'student_name',
            'student_email',
            'title',
            'bio',
            'profile_image',
            'is_public',
            'theme',
            'public_url',
            'projects_section_enabled',
            'linkedin_enabled',
            'linkedin_url',
            'github_enabled',
            'github_url',
            'instagram_enabled',
            'instagram_url',
            'tiktok_enabled',
            'tiktok_url',
            'social_other_enabled',
            'social_other_label',
            'social_other_url',
            'resume_enabled',
            'resume_file',
            'resume_file_url',
            'items',
            'items_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'student', 'public_url', 'resume_file_url', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        """Get count of visible portfolio items"""
        return obj.items.filter(is_visible=True).count()

    def get_student_name(self, obj):
        """Get student's full name"""
        return obj.student.get_full_name() or obj.student.email

    def get_student_email(self, obj):
        """Get student's email"""
        return obj.student.email

    def get_resume_file_url(self, obj):
        return _absolute_file_url(self.context.get('request'), obj.resume_file)


class PortfolioItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating portfolio items"""
    project_submission_id = serializers.IntegerField(write_only=True, required=False)
    share_token = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = PortfolioItem
        fields = [
            'project_submission_id',
            'share_token',
            'title',
            'description',
            'featured',
            'order',
            'category',
            'tags',
            'skills_demonstrated',
            'thumbnail_image',
            'demo_url',
            'screenshots',
            'is_visible',
        ]

    def validate(self, attrs):
        """Validate that project submission belongs to user and is graded"""
        project_submission_id = attrs.get('project_submission_id')
        share_token = attrs.get('share_token')
        user = self.context['request'].user
        portfolio = self.context.get('portfolio')

        # If share_token is provided, use it to find the submission
        if share_token:
            try:
                project_submission = ProjectSubmission.objects.get(share_token=share_token)
            except ProjectSubmission.DoesNotExist:
                raise serializers.ValidationError({"share_token": "Invalid share token"})
        elif project_submission_id:
            try:
                project_submission = ProjectSubmission.objects.get(id=project_submission_id)
            except ProjectSubmission.DoesNotExist:
                raise serializers.ValidationError({"project_submission_id": "Project submission not found"})
        else:
            raise serializers.ValidationError({"non_field_errors": ["Either project_submission_id or share_token is required"]})

        # Verify ownership
        if project_submission.student != user:
            raise serializers.ValidationError({"non_field_errors": ["You can only add your own project submissions to your portfolio"]})

        # Verify it's graded
        if project_submission.status != 'GRADED':
            raise serializers.ValidationError({"non_field_errors": [f"Only graded project submissions can be added to portfolio. Current status: {project_submission.status}"]})

        # Check for duplicate - ensure this submission isn't already in the portfolio
        if portfolio:
            existing_item = PortfolioItem.objects.filter(portfolio=portfolio, project_submission=project_submission).first()
            if existing_item:
                raise serializers.ValidationError({"non_field_errors": ["This project submission is already in your portfolio"]})

        attrs['project_submission'] = project_submission
        return attrs

    def create(self, validated_data):
        """Create portfolio item"""
        portfolio = self.context['portfolio']
        project_submission = validated_data.pop('project_submission')
        validated_data.pop('project_submission_id', None)
        validated_data.pop('share_token', None)

        # Set default title if not provided
        if not validated_data.get('title'):
            validated_data['title'] = project_submission.project.title

        portfolio_item = PortfolioItem.objects.create(
            portfolio=portfolio,
            project_submission=project_submission,
            **validated_data
        )
        return portfolio_item


class PublicPortfolioItemSerializer(serializers.ModelSerializer):
    """Serializer for public portfolio items (public view)"""
    project_details = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioItem
        fields = [
            'id',
            'title',
            'description',
            'featured',
            'category',
            'tags',
            'skills_demonstrated',
            'thumbnail_image',
            'demo_url',
            'screenshots',
            'project_details',
            'created_at',
        ]

    def get_project_details(self, obj):
        """Get project submission details for public view"""
        if obj.project_submission:
            serializer = PublicProjectSubmissionSerializer(
                obj.project_submission,
                context=self.context
            )
            return serializer.data
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        data["thumbnail_image"] = _absolute_file_url(request, instance.thumbnail_image)
        return data


class PublicPortfolioSerializer(serializers.ModelSerializer):
    """Serializer for public portfolio view — only safe, enabled link data in public_links."""
    items = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    public_links = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            'id',
            'title',
            'bio',
            'profile_image',
            'theme',
            'student_name',
            'projects_section_enabled',
            'public_links',
            'items',
            'created_at',
        ]

    def get_profile_image(self, obj):
        return _absolute_file_url(self.context.get('request'), obj.profile_image)

    def get_items(self, obj):
        """Get visible portfolio items"""
        visible_items = obj.items.filter(is_visible=True).order_by('-featured', 'order', '-created_at')
        return PublicPortfolioItemSerializer(visible_items, many=True, context=self.context).data

    def get_student_name(self, obj):
        """Get student's full name"""
        return obj.student.get_full_name() or obj.student.email

    def get_public_links(self, obj):
        """
        Enabled links only (for nav + header). projects_section mirrors projects_section_enabled.
        """
        request = self.context.get('request')
        urls = {}
        if obj.linkedin_enabled and (obj.linkedin_url or "").strip():
            urls['linkedin'] = obj.linkedin_url.strip()
        if obj.github_enabled and (obj.github_url or "").strip():
            urls['github'] = obj.github_url.strip()
        if obj.instagram_enabled and (obj.instagram_url or "").strip():
            urls['instagram'] = obj.instagram_url.strip()
        if obj.tiktok_enabled and (obj.tiktok_url or "").strip():
            urls['tiktok'] = obj.tiktok_url.strip()
        if obj.social_other_enabled and (obj.social_other_url or "").strip():
            urls['other'] = {
                'label': (obj.social_other_label or 'Link').strip() or 'Link',
                'url': obj.social_other_url.strip(),
            }
        resume_url = None
        if obj.resume_enabled and obj.resume_file:
            resume_url = _absolute_file_url(request, obj.resume_file)
            if resume_url:
                urls['resume'] = resume_url

        return {
            'show_projects': obj.projects_section_enabled,
            'urls': urls,
        }

