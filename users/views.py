from collections import Counter

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.mail import send_mail
from django.db.models import Avg, Count
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View

from gigs.models import Gig
from jobs.models import Job
from ai_engine.matching import rank_jobs_for_freelancer, rank_gigs_for_client
from .forms import (
    ProfileForm, ClientProfileForm, RegisterForm, NIDVerificationForm,
    WorkExperienceForm, EducationForm, CertificationForm,
)
from .models import WorkExperience, Education, Certification

User = get_user_model()


# ==========================================
# Email Verification Utilities
# ==========================================


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{getattr(user, 'email_verified', False)}"


email_verification_token = EmailVerificationTokenGenerator()


def send_verification_email(user, request):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verify_url = request.build_absolute_uri(
        f"/auth/verify-email/{uid}/{token}/"
    )

    subject = "Verify your Gigframe email"
    message = render_to_string(
        "users/verification_email.html",
        {
            "user": user,
            "verify_url": verify_url,
        },
    )
    send_mail(subject, message, None, [user.email])


# ==========================================
# Authentication Views
# ==========================================


class RegisterView(View):
    template_name = "users/register.html"

    def get(self, request):
        return render(request, self.template_name, {"form": RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(user, request)
            login(request, user)
            return redirect("home")
        return render(request, self.template_name, {"form": form})


class VerifyEmailView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and email_verification_token.check_token(
            user, token
        ):
            user.email_verified = True
            user.save()
            return render(request, "users/email_verified_success.html")
        else:
            return render(request, "users/email_verified_invalid.html")


class LoginView(DjangoLoginView):
    template_name = "users/login.html"
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def switch_role(request):
    """
    Lets a Freelancer become a Client or vice versa, on the same
    account — mirrors Fiverr's "Switch to Selling" toggle. Admins
    can't switch (there's no path into this view for them anyway,
    since the button is only ever shown on Freelancer/Client
    dashboards). All existing data (gigs, jobs, proposals, contracts)
    stays attached to the user by foreign key, so nothing is lost
    when switching back and forth.

    POST-only: flipping someone's role is a real state change, not
    something a GET request (which browsers/crawlers can trigger
    accidentally via prefetching) should ever be able to do.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = request.user

    if user.role == User.Role.FREELANCER:
        user.role = User.Role.CLIENT
    elif user.role == User.Role.CLIENT:
        user.role = User.Role.FREELANCER
    # Admins have no switch button pointing here, so no ADMIN branch needed.

    user.save(update_fields=["role"])
    return redirect("home")


# ==========================================
# Navigation & Dashboard Views
# ==========================================


class DashboardRouter(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return self._public_home(request)

        user = request.user

        if user.role == "FREELANCER":
            return self._freelancer_dashboard(request, user)
        elif user.role == "CLIENT":
            return self._client_dashboard(request, user)
        else:
            return redirect("/control-panel/")

    def _public_home(self, request):
        """
        Homepage for anonymous visitors. Builds a 'most popular gigs'
        section broken out by category (tabs), ranked by the
        freelancer's average review rating, then newest first.
        """
        popular_gigs_by_category = []
        for value, label in Gig.CATEGORY_CHOICES:
            gigs = (
                Gig.objects.filter(is_active=True, category=value)
                .annotate(freelancer_rating=Avg("freelancer__reviews_received__rating"))
                .order_by("-freelancer_rating", "-created_at")[:5]
            )
            if gigs:
                popular_gigs_by_category.append(
                    {"value": value, "label": label, "gigs": gigs}
                )

        context = {"popular_gigs_by_category": popular_gigs_by_category}
        return render(request, "home.html", context)

    def _freelancer_dashboard(self, request, user):
        open_jobs = Job.objects.filter(is_open=True)

        if user.skills:
            recommended_jobs = rank_jobs_for_freelancer(user, open_jobs)[:5]
        else:
            recommended_jobs = list(open_jobs.order_by("-created_at")[:5])

        # "Highest budget": the best-paying open jobs, skipping any job
        # already shown in "Jobs you may like" so the two rows never repeat.
        shown_ids = [job.pk for job in recommended_jobs]
        highest_budget_jobs = list(
            open_jobs.exclude(pk__in=shown_ids).order_by("-budget")[:5]
        )

        context = {
            "recommended_jobs": recommended_jobs,
            "highest_budget_jobs": highest_budget_jobs,
        }
        return render(request, "dashboards/freelancer_dashboard.html", context)

    def _client_dashboard(self, request, user):
        # Categories the client explicitly chose on their profile.
        chosen = [c.strip() for c in user.needed_categories.split(",") if c.strip()]

        active_gigs = Gig.objects.filter(is_active=True)
        if chosen:
            # An explicit choice wins: only consider gigs in those categories.
            active_gigs = active_gigs.filter(category__in=chosen)

        # Text describing what the client needs. Bio first, because the
        # embedding model only reads the beginning of long text.
        parts = []
        if user.bio:
            parts.append(user.bio)
        if chosen:
            parts.append("Looking for freelancers in: " + ", ".join(chosen))
        else:
            # No categories chosen, so fall back to their recent job posts.
            latest_jobs = Job.objects.filter(client=user).order_by("-created_at")[:3]
            parts += [f"{j.title}. {j.description} {j.required_skills}" for j in latest_jobs]
        need_text = " ".join(parts).strip()

        if need_text:
            recommended_gigs = rank_gigs_for_client(need_text, active_gigs, top_n=5)
        else:
            # Nothing to compare against yet, so show the newest gigs.
            recommended_gigs = list(active_gigs.order_by("-created_at")[:5])

        context = {
            "recommended_gigs": recommended_gigs,
            "ai_matched": bool(need_text),
        }
        return render(request, "dashboards/client_dashboard.html", context)


# ==========================================
# Profile Views
# ==========================================


def view_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    gigs = (
        profile_user.gigs.filter(is_active=True)
        if profile_user.role == "FREELANCER"
        else None
    )

    skill_list = (
        [s.strip() for s in profile_user.skills.split(",") if s.strip()]
        if profile_user.skills
        else []
    )

    reviews = profile_user.reviews_received.all()
    review_count = reviews.count()
    average_rating = None
    if review_count > 0:
        average_rating = round(
            sum(r.rating for r in reviews) / review_count, 1
        )

    return render(
        request,
        "users/profile.html",
        {
            "profile_user": profile_user,
            "gigs": gigs,
            "skill_list": skill_list,
            "reviews": reviews,
            "review_count": review_count,
            "average_rating": average_rating,
        },
    )


@login_required
def edit_profile(request):
    is_client = request.user.role == User.Role.CLIENT
    FormClass = ClientProfileForm if is_client else ProfileForm

    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("view_profile", username=request.user.username)
    else:
        form = FormClass(instance=request.user)

    context = {"form": form}
    if not is_client:
        context.update({
            "work_experiences": request.user.work_experiences.all(),
            "education_entries": request.user.education_entries.all(),
            "certifications": request.user.certifications.all(),
        })
    return render(request, "users/profile_edit.html", context)


@login_required
def resend_verification_email(request):
    if not request.user.email_verified:
        send_verification_email(request.user, request)
    return redirect("home")


@login_required
def submit_nid_verification(request):
    if request.method == "POST":
        form = NIDVerificationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.verification_status = User.VerificationStatus.PENDING
            user.save()
            return redirect("view_profile", username=request.user.username)
    else:
        form = NIDVerificationForm(instance=request.user)

    return render(request, "users/submit_verification.html", {"form": form})


# ==========================================
# Work Experience / Education / Certification Views
# ==========================================


@login_required
def add_work_experience(request):
    if request.method == "POST":
        form = WorkExperienceForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            return redirect("edit_profile")
    else:
        form = WorkExperienceForm()
    return render(request, "users/add_work_experience.html", {"form": form})


@login_required
def delete_work_experience(request, pk):
    entry = get_object_or_404(WorkExperience, pk=pk, user=request.user)
    entry.delete()
    return redirect("edit_profile")


@login_required
def add_education(request):
    if request.method == "POST":
        form = EducationForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            return redirect("edit_profile")
    else:
        form = EducationForm()
    return render(request, "users/add_education.html", {"form": form})


@login_required
def delete_education(request, pk):
    entry = get_object_or_404(Education, pk=pk, user=request.user)
    entry.delete()
    return redirect("edit_profile")


@login_required
def add_certification(request):
    if request.method == "POST":
        form = CertificationForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            return redirect("edit_profile")
    else:
        form = CertificationForm()
    return render(request, "users/add_certification.html", {"form": form})


@login_required
def delete_certification(request, pk):
    entry = get_object_or_404(Certification, pk=pk, user=request.user)
    entry.delete()
    return redirect("edit_profile")