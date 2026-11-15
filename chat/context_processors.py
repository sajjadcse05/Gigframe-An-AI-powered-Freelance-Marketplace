from django.db.models import Q

from .models import Conversation, Message


def unread_chat_count(request):
    """
    Runs on every page load (once registered in settings.py) so the
    navbar chat icon can show a live unread badge and a dropdown of
    recent conversations, without every view needing to pass this in.
    """
    if not request.user.is_authenticated:
        return {"nav_unread_messages": 0, "nav_conversations": []}

    conversations = Conversation.objects.filter(
        Q(participant_a=request.user) | Q(participant_b=request.user)
    )[:8]  # most recent 8, for the dropdown preview

    # Attach "other participant" and "unread count from them" onto each
    # conversation object here in Python — templates can't call methods
    # with arguments, so we precompute everything the dropdown needs.
    for conv in conversations:
        conv.other = conv.other_user(request.user)
        conv.unread_from_other = conv.messages.filter(is_read=False).exclude(sender=request.user).count()

    total_unread = Message.objects.filter(
        Q(conversation__participant_a=request.user) | Q(conversation__participant_b=request.user)
    ).exclude(sender=request.user).filter(is_read=False).count()

    return {
        "nav_unread_messages": total_unread,
        "nav_conversations": conversations,
    }