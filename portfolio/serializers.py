from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Portfolio, PortfolioItem
from courses.models import ProjectSubmission
from courses.serializers import PublicProjectSubmissionSerializer

User = get_user_model()


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


class PortfolioSerializer(serializers.ModelSerializer):
    """Serializer for portfolio (student view)"""
    items = PortfolioItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_email = serializers.SerializerMethodField()

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
            'custom_url',
            'theme',
            'public_url',
            'items',
            'items_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'student', 'public_url', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        """Get count of visible portfolio items"""
        return obj.items.filter(is_visible=True).count()

    def get_student_name(self, obj):
        """Get student's full name"""
        return obj.student.get_full_name() or obj.student.email

    def get_student_email(self, obj):
        """Get student's email"""
        return obj.student.email


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
            'category',
            'tags',
            'skills_demonstrated',
            'thumbnail_image',
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


class PublicPortfolioSerializer(serializers.ModelSerializer):
    """Serializer for public portfolio view"""
    items = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            'id',
            'title',
            'bio',
            'profile_image',
            'theme',
            'student_name',
            'items',
            'created_at',
        ]

    def get_items(self, obj):
        """Get visible portfolio items"""
        visible_items = obj.items.filter(is_visible=True).order_by('-featured', 'order', '-created_at')
        return PublicPortfolioItemSerializer(visible_items, many=True, context=self.context).data

    def get_student_name(self, obj):
        """Get student's full name"""
        return obj.student.get_full_name() or obj.student.email

