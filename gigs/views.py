from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from ai_engine.pricing import suggest_price
from .forms import GigForm, GigOrderForm
from .models import Gig, GigImage

CATEGORY_SLUG_MAP = {
    "web-development": "Web Development",
    "graphic-design": "Graphic Design",
    "digital-marketing": "Digital Marketing",
    "content-writing": "Content Writing",
    "video-editing": "Video Editing",
    "virtual-assistant": "Virtual Assistant",
}


class GigListView(ListView):
    model = Gig
    template_name = "gigs/gig_list.html"
    context_object_name = "gigs"
    paginate_by = 12

    def get_queryset(self):
        queryset = Gig.objects.filter(is_active=True)

        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            category_name = CATEGORY_SLUG_MAP.get(category_slug)
            if category_name is None:
                raise Http404("Unknown category")
            queryset = queryset.filter(category=category_name)

        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(tags__icontains=search_query)
                | Q(category__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get("category_slug")
        context["selected_category_name"] = CATEGORY_SLUG_MAP.get(category_slug) if category_slug else None
        context["category_slugs"] = CATEGORY_SLUG_MAP
        context["search_query"] = self.request.GET.get("q", "")
        return context


class GigDetailView(DetailView):
    model = Gig
    template_name = "gigs/gig_detail.html"
    context_object_name = "gig"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tags_raw = self.object.tags
        context["tag_list"] = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        freelancer = self.object.freelancer
        reviews = freelancer.reviews_received.all()
        review_count = reviews.count()
        average_rating = round(sum(r.rating for r in reviews) / review_count, 1) if review_count > 0 else None

        context["freelancer_reviews"] = reviews[:5]
        context["freelancer_review_count"] = review_count
        context["freelancer_average_rating"] = average_rating

        return context


class GigCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Gig
    form_class = GigForm
    template_name = "gigs/gig_form.html"

    def test_func(self):
        return self.request.user.role == "FREELANCER"

    def form_valid(self, form):
        form.instance.freelancer = self.request.user
        response = super().form_valid(form)

        for image_file in self.request.FILES.getlist("images"):
            GigImage.objects.create(gig=self.object, image=image_file)

        return response

    def get_success_url(self):
        return "/gigs/mine/"


class GigUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Lets a Freelancer edit their own gig listing. Unlike Jobs, Gigs
    have no "hired/locked" state to worry about — a gig is a standing
    service listing, not tied to a single contract, so it can always
    be edited by its owner. New images uploaded on edit are added
    alongside existing ones rather than replacing them.
    """
    model = Gig
    form_class = GigForm
    template_name = "gigs/gig_form.html"

    def test_func(self):
        return self.get_object().freelancer == self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)

        for image_file in self.request.FILES.getlist("images"):
            GigImage.objects.create(gig=self.object, image=image_file)

        return response

    def get_success_url(self):
        return "/gigs/mine/"


@login_required
def gig_delete(request, pk):
    """Deletes a gig listing. No hire-lock needed — Gigs never own a Contract directly."""
    gig = get_object_or_404(Gig, pk=pk)

    if gig.freelancer != request.user:
        raise PermissionDenied("You can only delete your own gig listings.")

    if request.method == "POST":
        gig.delete()

    return redirect("my_gigs")


@login_required
def order_gig(request, pk):
    """
    Lets a Client hire this Gig's freelancer directly with a custom
    budget, instead of manually posting a Job and waiting for a
    proposal. Creates a Job, an auto-accepted Proposal, and a
    Contract in one step, then sends the client straight to funding
    it — same end result as the normal Job → Proposal → Accept flow,
    just compressed into one action from the Gig page.
    """
    gig = get_object_or_404(Gig, pk=pk)

    if request.user.role != "CLIENT":
        raise PermissionDenied("Only clients can hire a freelancer.")

    # Mirrors the self-dealing guard on submit_proposal — relevant now
    # that a Freelancer can switch into Client mode and land on their
    # own gig page.
    if gig.freelancer == request.user:
        raise PermissionDenied("You can't hire yourself through your own gig listing.")

    if request.method == "POST":
        form = GigOrderForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]

            from jobs.models import Job, Proposal
            from contracts.models import Contract

            job = Job.objects.create(
                client=request.user,
                title=f"Direct order: {gig.title}",
                description=f"Client-initiated order based on the gig \"{gig.title}\".\n\n{gig.description}",
                category=gig.category,
                budget=amount,
                deadline=timezone.localdate() + timedelta(days=gig.delivery_days),
                required_skills="",
                is_open=False,
            )

            proposal = Proposal.objects.create(
                job=job,
                freelancer=gig.freelancer,
                cover_letter=f"Auto-generated proposal from direct gig order for \"{gig.title}\".",
                quoted_price=amount,
                delivery_days=gig.delivery_days,
                status=Proposal.Status.ACCEPTED,
            )

            contract, _ = Contract.objects.get_or_create(
                job=job,
                proposal=proposal,
                defaults={
                    "client": request.user,
                    "freelancer": gig.freelancer,
                    "amount": amount,
                },
            )

            return redirect("contract_detail", pk=contract.pk)
    else:
        form = GigOrderForm(initial={"amount": gig.price})

    return render(request, "gigs/gig_order.html", {"gig": gig, "form": form})


@login_required
def my_gigs(request):
    gigs = Gig.objects.filter(freelancer=request.user)
    return render(request, "gigs/my_gigs.html", {"gigs": gigs})


def price_suggestion_api(request):
    category = request.GET.get("category", "")
    try:
        delivery_days = int(request.GET.get("delivery_days", 7))
    except ValueError:
        delivery_days = 7

    result = suggest_price(category, delivery_days)
    if result is None:
        return JsonResponse({"available": False})

    low, high = result
    return JsonResponse({"available": True, "low": low, "high": high})


@login_required
def gig_image_delete(request, pk):
    """Deletes a single image from a gig's gallery. Freelancer-owned only."""
    image = get_object_or_404(GigImage, pk=pk)

    if image.gig.freelancer != request.user:
        raise PermissionDenied("You can only delete images from your own gig.")

    gig_pk = image.gig.pk
    if request.method == "POST":
        image.delete()

    return redirect("gig_edit", pk=gig_pk)