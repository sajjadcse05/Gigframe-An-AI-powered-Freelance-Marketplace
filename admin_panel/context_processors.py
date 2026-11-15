from support.models import ContactMessage


def open_support_messages(request):
    """
    Makes the count of unresolved Contact form submissions available
    to every template that extends admin_panel/base.html — not just
    the Dashboard — so the sidebar badge stays accurate no matter
    which admin page is currently open.
    """
    if request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN":
        count = ContactMessage.objects.filter(is_resolved=False).count()
        return {"open_support_messages": count}
    return {}