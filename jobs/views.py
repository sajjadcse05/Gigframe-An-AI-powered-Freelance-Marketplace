from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from ai_engine.matching import rank_jobs_for_freelancer
from ai_engine.pricing import suggest_price
from notifications.models import Notification
from .forms import JobForm, ProposalForm
from .models import Job, Proposal

CATEGORY_SLUG_MAP = {
    "web-development": "Web Development",
    "graphic-design": "Graphic Design",
    "digital-marketing": "Digital Marketing",
    "content-writing": "Content Writing",
    "video-editing": "Video Editing",
    "virtual-assistant": "Virtual Assistant",
}


class JobListView(ListView):
    model = Job
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 12

    def get_queryset(self):
        queryset = Job.objects.filter(is_open=True)

        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            category_name = CATEGORY_SLUG_MAP.get(category_slug)
            if category_name is None:
                raise Http404("Unknown category")
            queryset = queryset.filter(category=category_name)

        user = self.request.user
        if user.is_authenticated and user.role == "FREELANCER" and user.skills:
            return rank_jobs_for_freelancer(user, queryset)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get("category_slug")
        context["selected_category_name"] = CATEGORY_SLUG_MAP.get(category_slug) if category_slug else None
        context["category_slugs"] = CATEGORY_SLUG_MAP
        return context


class JobDetailView(DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        skills_raw = self.object.required_skills
        context["skill_list"] = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []

        user = self.request.user
        if user.is_authenticated and user.role == "FREELANCER":
            context["proposal_form"] = ProposalForm()
            context["already_applied"] = Proposal.objects.filter(job=self.object, freelancer=user).exists()
        return context


class JobCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def test_func(self):
        return self.request.user.role == "CLIENT"

    def form_valid(self, form):
        form.instance.client = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return "/jobs/mine/"


class JobUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Lets a Client edit their own job posting — but only while it's
    still open. Once a freelancer has been hired (a Contract exists,
    which also flips is_open to False), the job's terms are locked,
    since changing scope/budget after hiring would be unfair to the
    freelancer who quoted against the original posting.
    """
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def test_func(self):
        job = self.get_object()
        return job.client == self.request.user and job.is_open

    def get_success_url(self):
        return "/jobs/mine/"


@login_required
def job_delete(request, pk):
    """
    Deletes a job posting. Same rule as editing: blocked once a
    freelancer has been hired, both to protect the freelancer and
    because deleting the Job would cascade-delete its Contract
    (Contract.job is a required OneToOneField with on_delete=CASCADE),
    silently destroying real payment/escrow records.
    """
    job = get_object_or_404(Job, pk=pk)

    if job.client != request.user:
        raise PermissionDenied("You can only delete your own job postings.")

    if not job.is_open:
        raise PermissionDenied("This job can't be deleted — a freelancer has already been hired for it.")

    if request.method == "POST":
        job.delete()

    return redirect("my_jobs")


@login_required
def job_price_suggestion_api(request):
    category = request.GET.get("category")
    delivery_days = request.GET.get("delivery_days")

    if not category or not delivery_days:
        return JsonResponse({"suggestion": None})

    try:
        delivery_days = int(delivery_days)
    except ValueError:
        return JsonResponse({"suggestion": None})

    result = suggest_price(category, delivery_days)
    if result is None:
        return JsonResponse({"suggestion": None})

    low, high = result
    return JsonResponse({"suggestion": {"low": low, "high": high}})


@login_required
def my_jobs(request):
    jobs = Job.objects.filter(client=request.user)
    return render(request, "jobs/my_jobs.html", {"jobs": jobs})


@login_required
def submit_proposal(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)

    if request.user.role != "FREELANCER":
        raise PermissionDenied("Only freelancers can submit proposals.")

    if job.client == request.user:
        raise PermissionDenied("You can't submit a proposal on your own job posting.")

    if request.method == "POST":
        form = ProposalForm(request.POST)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.job = job
            proposal.freelancer = request.user
            proposal.save()

            Notification.objects.create(
                recipient=job.client,
                message=f"{request.user.username} submitted a proposal on \"{job.title}\"",
                link=f"/jobs/{job.pk}/proposals/",
            )

    return redirect("job_detail", pk=job_pk)


@login_required
def job_proposals(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)

    if job.client != request.user:
        raise PermissionDenied("You can only view proposals on your own jobs.")

    proposals = job.proposals.all()
    return render(request, "jobs/job_proposals.html", {"job": job, "proposals": proposals})


@login_required
def update_proposal_status(request, proposal_pk, new_status):
    proposal = get_object_or_404(Proposal, pk=proposal_pk)

    if proposal.job.client != request.user:
        raise PermissionDenied("You can only manage proposals on your own jobs.")

    if new_status in ["ACCEPTED", "REJECTED"]:
        proposal.status = new_status
        proposal.save()

        verb = "accepted" if new_status == "ACCEPTED" else "rejected"
        Notification.objects.create(
            recipient=proposal.freelancer,
            message=f"Your proposal on \"{proposal.job.title}\" was {verb}",
            link=f"/jobs/{proposal.job.pk}/",
        )

        if new_status == "ACCEPTED":
            from contracts.models import Contract
            contract, _ = Contract.objects.get_or_create(
                job=proposal.job,
                proposal=proposal,
                defaults={
                    "client": proposal.job.client,
                    "freelancer": proposal.freelancer,
                    "amount": proposal.quoted_price,
                },
            )
            proposal.job.is_open = False
            proposal.job.save()

            return redirect("contract_detail", pk=contract.pk)

    return redirect("job_proposals", job_pk=proposal.job.pk)


@login_required
def my_proposals(request):
    proposals = Proposal.objects.filter(freelancer=request.user).select_related("job")
    return render(request, "jobs/my_proposals.html", {"proposals": proposals})