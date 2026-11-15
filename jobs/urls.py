from django.urls import path

from .views import (
    JobListView, JobDetailView, JobCreateView, JobUpdateView, job_delete, my_jobs,
    submit_proposal, job_proposals, update_proposal_status, my_proposals,
    job_price_suggestion_api,
)

urlpatterns = [
    path("", JobListView.as_view(), name="job_list"),
    path("create/", JobCreateView.as_view(), name="job_create"),
    path("mine/", my_jobs, name="my_jobs"),
    path("api/price-suggestion/", job_price_suggestion_api, name="job_price_suggestion_api"),
    path("category/<str:category_slug>/", JobListView.as_view(), name="job_list_by_category"),
    path("<int:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("<int:pk>/edit/", JobUpdateView.as_view(), name="job_edit"),
    path("<int:pk>/delete/", job_delete, name="job_delete"),
    path("<int:job_pk>/apply/", submit_proposal, name="submit_proposal"),
    path("<int:job_pk>/proposals/", job_proposals, name="job_proposals"),
    path("proposals/<int:proposal_pk>/<str:new_status>/", update_proposal_status, name="update_proposal_status"),
    path("proposals/mine/", my_proposals, name="my_proposals"),
]