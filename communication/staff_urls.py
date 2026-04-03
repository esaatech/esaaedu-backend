from django.urls import path

from communication.staff_messages_views import (
    StaffMessagesAdminUnreadApiView,
    StaffMessagesDeliveryIssuesApiView,
    StaffMessagesLogDetailApiView,
    StaffMessagesSendApiView,
    StaffMessagesTeacherUnreadApiView,
    StaffMessagesUserSearchApiView,
)

urlpatterns = [
    path(
        "delivery-issues/",
        StaffMessagesDeliveryIssuesApiView.as_view(),
        name="staff_messages_delivery_issues",
    ),
    path("admin-unread/", StaffMessagesAdminUnreadApiView.as_view(), name="staff_messages_admin_unread"),
    path(
        "teacher-unread/",
        StaffMessagesTeacherUnreadApiView.as_view(),
        name="staff_messages_teacher_unread",
    ),
    path("logs/<uuid:log_id>/", StaffMessagesLogDetailApiView.as_view(), name="staff_messages_log_detail"),
    path("users/search/", StaffMessagesUserSearchApiView.as_view(), name="staff_messages_user_search"),
    path("send/", StaffMessagesSendApiView.as_view(), name="staff_messages_send"),
]
