from django.urls import path

from .views import (
    inbox,
    start_conversation,
    conversation_detail,
    send_message,
    poll_messages,
    widget_init,
)

urlpatterns = [
    path("", inbox, name="chat_inbox"),
    path("start/<int:user_id>/", start_conversation, name="start_conversation"),
    path("<int:pk>/", conversation_detail, name="conversation_detail"),
    path("<int:pk>/send/", send_message, name="send_message"),
    path("<int:pk>/poll/<int:after_id>/", poll_messages, name="poll_messages"),
    path("widget/init/<int:user_id>/", widget_init, name="chat_widget_init"),
]