from django.urls import path

from . import views

app_name = "pos"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("billing/", views.billing, name="billing"),
    path("billing/checkout/", views.checkout, name="checkout"),
    path("transactions/", views.sales, name="sales"),
    path("my-sales/", views.my_sales, name="mine"),
    path("bills/<int:pk>/", views.sale_detail, name="sale_detail"),
    path("bills/<int:pk>/void/", views.sale_void, name="sale_void"),
    path("returns/", views.returns, name="returns"),
    path("returns/item/<int:pk>/", views.return_item, name="return_item"),
    path("ledger/", views.ledger, name="ledger"),
    path("ledger/expense/new/", views.expense_new, name="expense_new"),
]

for c in views.CRUD:
    k, s = c["key"], c["slug"]
    urlpatterns += [
        path(f"{s}/", c["list"], name=f"{k}_list"),
        path(f"{s}/new/", c["new"], name=f"{k}_new"),
        path(f"{s}/<int:pk>/edit/", c["edit"], name=f"{k}_edit"),
        path(f"{s}/<int:pk>/delete/", c["delete"], name=f"{k}_delete"),
    ]
