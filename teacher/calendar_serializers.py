from rest_framework import serializers


class StaffWeekCalendarEventSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    course_id = serializers.CharField()
    course_title = serializers.CharField()
    class_id = serializers.CharField()
    class_name = serializers.CharField()
    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    status = serializers.CharField()
    event_title = serializers.CharField(allow_blank=True)
    class_detail_url = serializers.CharField(allow_blank=True)


class StaffClassDialogSerializer(serializers.Serializer):
    class_id = serializers.CharField()
    class_name = serializers.CharField()
    course_title = serializers.CharField()
    teacher_name = serializers.CharField(allow_blank=True)
    dialog_html = serializers.CharField()


class StaffTeacherDialogSerializer(serializers.Serializer):
    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    dialog_html = serializers.CharField()
