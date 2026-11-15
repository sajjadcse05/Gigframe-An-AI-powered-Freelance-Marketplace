from django.urls import path

from .views import (
    GigListView, GigDetailView, GigCreateView, GigUpdateView, gig_delete,
    gig_image_delete, order_gig, my_gigs, price_suggestion_api,
)

urlpatterns = [
    path("", GigListView.as_view(), name="gig_list"),
    path("create/", GigCreateView.as_view(), name="gig_create"),
    path("mine/", my_gigs, name="my_gigs"),
    path("api/price-suggestion/", price_suggestion_api, name="price_suggestion_api"),
    path("category/<str:category_slug>/", GigListView.as_view(), name="gig_list_by_category"),
    path("<int:pk>/", GigDetailView.as_view(), name="gig_detail"),
    path("<int:pk>/edit/", GigUpdateView.as_view(), name="gig_edit"),
    path("<int:pk>/delete/", gig_delete, name="gig_delete"),
    path("<int:pk>/order/", order_gig, name="gig_order"),
    path("images/<int:pk>/delete/", gig_image_delete, name="gig_image_delete"),
]