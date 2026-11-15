from .models import Notification


def notifications(request):
    """
    A context processor runs automatically on EVERY template render
    (once registered in settings.py), so the navbar bell icon can show
    unread notifications on any page, without every single view having
    to remember to pass that data in manually.
    """
    if request.user.is_authenticated:
        qs = Notification.objects.filter(recipient=request.user)
        return {
            "nav_notifications": qs[:6],              # latest 6, for the dropdown preview
            "nav_unread_count": qs.filter(is_read=False).count(),
        }
    return {"nav_notifications": [], "nav_unread_count": 0}