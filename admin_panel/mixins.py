from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Every single view in this app uses this — it's the one gate that
    makes the whole custom admin panel actually admin-only. Anyone
    whose role isn't ADMIN gets a 403, not just a redirect (a redirect
    to login would wrongly imply a non-admin could get in by logging
    in differently — a straight 403 is the honest response: "you are
    logged in, but you are not allowed here").
    """

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "ADMIN"

    def handle_no_permission(self):
        raise PermissionDenied("Admin access only.")