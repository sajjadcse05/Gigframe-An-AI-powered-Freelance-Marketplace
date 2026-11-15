from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Notification


@login_required
def notification_list(request):
    """Full notifications page — also marks everything as read when visited."""
    notifications = Notification.objects.filter(recipient=request.user)
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, "notifications/notification_list.html", {"notifications": notifications})


@login_required
def mark_read_and_redirect(request, pk):
    """
    Clicking a single notification in the dropdown: mark it read,
    then send the user to whatever it's about (e.g. the proposals page).
    """
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    note.is_read = True
    note.save()
    return redirect(note.link or "home")