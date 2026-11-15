from django.urls import path

from .views import (
    RegisterView, LoginView, logout_view, view_profile, edit_profile,
    VerifyEmailView, resend_verification_email, submit_nid_verification,
    add_work_experience, delete_work_experience,
    add_education, delete_education,
    add_certification, delete_certification,
    switch_role,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path("verify-email/<uidb64>/<token>/", VerifyEmailView.as_view(), name="verify_email"),
    path("verify-email/resend/", resend_verification_email, name="resend_verification"),
    path("verify-nid/", submit_nid_verification, name="submit_nid_verification"),
    path("switch-role/", switch_role, name="switch_role"),

    path("work-experience/add/", add_work_experience, name="add_work_experience"),
    path("work-experience/<int:pk>/delete/", delete_work_experience, name="delete_work_experience"),
    path("education/add/", add_education, name="add_education"),
    path("education/<int:pk>/delete/", delete_education, name="delete_education"),
    path("certification/add/", add_certification, name="add_certification"),
    path("certification/<int:pk>/delete/", delete_certification, name="delete_certification"),

    path("profile/edit/", edit_profile, name="edit_profile"),
    path("profile/<str:username>/", view_profile, name="view_profile"),
]