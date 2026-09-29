import json
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from .forms import ExpenseForm, ProductForm, StaffForm, SupplierForm
from .models import GST_RATE, LOW_STOCK, Expense, Product, Sale, SaleItem, SaleReturn, Supplier, User, money


# ---------- access control ----------
def admin_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_shop_admin:
            messages.error(request, "That page is for admins only.")
            return redirect("pos:billing")
        return view(request, *args, **kwargs)
    return wrapper


class AdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_shop_admin

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "That page is for admins only.")
            return redirect("pos:billing")
        return super().handle_no_permission()


@login_required
def home(request):
    return redirect("pos:dashboard" if request.user.is_shop_admin else "pos:billing")


# ---------- dashboard ----------
@admin_required
def dashboard(request):
    ok = Sale.objects.filter(is_void=False)
    revenue = ok.aggregate(t=Sum("total"))["t"] or Decimal(0)
    refunds = SaleReturn.objects.aggregate(t=Sum("refund"))["t"] or Decimal(0)
    expenses = Expense.objects.aggregate(t=Sum("amount"))["t"] or Decimal(0)
    by_payment = [(p, ok.filter(payment=p).aggregate(t=Sum("total"))["t"] or Decimal(0))
                  for p, _ in Sale.PAYMENTS]
    return render(request, "pos/dashboard.html", {
        "bills": ok.count(), "revenue": revenue, "refunds": refunds, "expenses": expenses,
        "net": revenue - refunds - expenses, "by_payment": by_payment,
        "low_stock": Product.objects.filter(stock__lte=LOW_STOCK),
    })


# ---------- CRUD for products / staff / suppliers ----------
def _cell(obj, col):
    v = getattr(obj, col[1])
    if callable(v):
        v = v()
    if v is None:
        return ""
    if len(col) > 2 and col[2] == "money":
        return f"₹{v:.2f}"
    return v


def make_crud(key, slug, _model, _form, title, singular, columns):
    list_name = f"pos:{key}_list"

    class ListV(AdminMixin, ListView):
        model = _model
        template_name = "pos/crud_list.html"

        def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            ctx["rows"] = [{
                "cells": [_cell(o, c) for c in columns],
                "edit": reverse(f"pos:{key}_edit", args=[o.pk]),
                "delete": reverse(f"pos:{key}_delete", args=[o.pk]),
            } for o in ctx["object_list"]]
            ctx.update(title=title, singular=singular, headers=[c[0] for c in columns],
                       new_url=reverse(f"pos:{key}_new"))
            return ctx

    class FormMixin(AdminMixin):
        model = _model
        form_class = _form
        template_name = "pos/crud_form.html"
        success_url = reverse_lazy(list_name)

        def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            editing = getattr(self, "object", None) is not None
            ctx.update(title=f"{'Edit' if editing else 'Add'} {singular.lower()}",
                       back_url=reverse(list_name))
            return ctx

        def form_valid(self, form):
            messages.success(self.request, f"{singular} saved.")
            return super().form_valid(form)

    class CreateV(FormMixin, CreateView):
        pass

    class UpdateV(FormMixin, UpdateView):
        pass

    class DeleteV(AdminMixin, View):
        def post(self, request, pk):
            obj = get_object_or_404(_model, pk=pk)
            if isinstance(obj, User) and (obj.pk == request.user.pk or obj.is_superuser):
                messages.error(request, "This account cannot be deleted.")
            else:
                obj.delete()
                messages.success(request, f"{singular} deleted.")
            return redirect(list_name)

    return {"key": key, "slug": slug, "list": ListV.as_view(), "new": CreateV.as_view(),
            "edit": UpdateV.as_view(), "delete": DeleteV.as_view()}


CRUD = [
    make_crud("product", "products", Product, ProductForm, "Products", "Product",
              [("Name", "name"), ("SKU", "sku"), ("Category", "category"),
               ("Price", "price", "money"), ("Stock", "stock"), ("Supplier", "supplier")]),
    make_crud("staff", "staff", User, StaffForm, "Staff", "Staff member",
              [("Name", "display_name"), ("Username", "username"),
               ("Role", "get_role_display"), ("Active", "is_active")]),
    make_crud("supplier", "suppliers", Supplier, SupplierForm, "Suppliers", "Supplier",
              [("Name", "name"), ("Phone", "phone"), ("City", "city"), ("Amount due", "due", "money")]),
]


# ---------- billing ----------
@login_required
def billing(request):
    products = [{"id": p.pk, "name": p.name, "sku": p.sku, "price": str(p.price), "stock": p.stock}
                for p in Product.objects.filter(stock__gt=0)]
    return render(request, "pos/billing.html",
                  {"products": products, "payments": [p for p, _ in Sale.PAYMENTS]})


@login_required
@require_POST
def checkout(request):
    """The cart lives in the browser; prices, stock and totals are re-checked here."""
    try:
        data = json.loads(request.body)
        disc = min(Decimal(100), max(Decimal(0), Decimal(str(data.get("discount") or 0))))
        pay = data.get("payment")
        wanted = {}
        for it in data.get("items", []):
            pid, qty = int(it["id"]), int(it["qty"])
            if qty < 1:
                raise ValueError
            wanted[pid] = wanted.get(pid, 0) + qty
    except (ValueError, TypeError, KeyError, InvalidOperation, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid bill data."}, status=400)
    if not wanted:
        return JsonResponse({"error": "Add at least one item."}, status=400)
    if pay not in dict(Sale.PAYMENTS):
        return JsonResponse({"error": "Choose a payment method."}, status=400)

    with transaction.atomic():
        products = Product.objects.select_for_update().in_bulk(list(wanted))
        for pid, qty in wanted.items():
            p = products.get(pid)
            if p is None or qty > p.stock:
                name = p.name if p else "a product"
                return JsonResponse({"error": f"Not enough stock for {name}."}, status=409)
        subtotal = sum((products[i].price * q for i, q in wanted.items()), Decimal(0))
        dv, tax, total = Sale.totals(subtotal, disc)
        sale = Sale.objects.create(cashier=request.user, discount_pct=disc, payment=pay,
                                   subtotal=subtotal, discount_amount=dv, tax=tax, total=total)
        for pid, qty in wanted.items():
            p = products[pid]
            SaleItem.objects.create(sale=sale, product=p, name=p.name, price=p.price, qty=qty)
            p.stock -= qty
            p.save(update_fields=["stock"])
    return JsonResponse({"receipt_url": reverse("pos:sale_detail", args=[sale.pk])})


# ---------- transactions ----------
@admin_required
def sales(request):
    return render(request, "pos/sales.html", {
        "title": "Transactions", "sales": Sale.objects.select_related("cashier")})


@login_required
def my_sales(request):
    return render(request, "pos/sales.html", {
        "title": "My sales", "sales": Sale.objects.select_related("cashier").filter(cashier=request.user)})


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("cashier").prefetch_related("items"), pk=pk)
    if not request.user.is_shop_admin and sale.cashier_id != request.user.pk:
        messages.error(request, "You can only view your own bills.")
        return redirect("pos:mine")
    return render(request, "pos/receipt.html", {"sale": sale})


@admin_required
@require_POST
def sale_void(request, pk):
    with transaction.atomic():
        sale = get_object_or_404(Sale.objects.select_for_update(), pk=pk)
        if not sale.is_void:
            for it in sale.items.all():
                if it.product_id:
                    Product.objects.filter(pk=it.product_id).update(stock=F("stock") + it.returnable)
            sale.is_void = True
            sale.save(update_fields=["is_void"])
            messages.success(request, f"{sale.invoice_no} voided and stock restored.")
    return redirect("pos:sales")


# ---------- returns ----------
@admin_required
def returns(request):
    inv = request.GET.get("invoice", "").strip()
    sale = None
    if inv:
        sale = Sale.objects.filter(invoice_no__iexact=inv, is_void=False).prefetch_related("items").first()
    return render(request, "pos/returns.html", {
        "invoice": inv, "sale": sale, "returns": SaleReturn.objects.select_related("sale")})


@admin_required
@require_POST
def return_item(request, pk):
    with transaction.atomic():
        item = get_object_or_404(SaleItem.objects.select_for_update().select_related("sale"),
                                 pk=pk, sale__is_void=False)
        try:
            qty = int(request.POST.get("qty", ""))
        except ValueError:
            qty = 0
        if not 1 <= qty <= item.returnable:
            messages.error(request, "Invalid return quantity.")
        else:
            sale = item.sale
            refund = money(item.price * qty * (1 - sale.discount_pct / 100) * (1 + GST_RATE))
            item.returned_qty += qty
            item.save(update_fields=["returned_qty"])
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(stock=F("stock") + qty)
            SaleReturn.objects.create(sale=sale, item_name=item.name, qty=qty, refund=refund,
                                      reason=request.POST.get("reason", "").strip()[:200] or "-")
            messages.success(request, f"Refunded ₹{refund:.2f} for {qty} × {item.name}.")
    return redirect(f"{reverse('pos:returns')}?invoice={item.sale.invoice_no}")


# ---------- ledger ----------
@admin_required
def ledger(request):
    entries = [(s.created_at, f"Sale {s.invoice_no}", s.total, Decimal(0))
               for s in Sale.objects.filter(is_void=False)]
    entries += [(r.created_at, f"Return {r.sale.invoice_no}", Decimal(0), r.refund)
                for r in SaleReturn.objects.select_related("sale")]
    entries += [(e.created_at, f"{e.category}: {e.note}", Decimal(0), e.amount)
                for e in Expense.objects.all()]
    entries.sort(key=lambda e: e[0])
    bal, rows = Decimal(0), []
    for when, label, money_in, money_out in entries:
        bal += money_in - money_out
        rows.append({"date": when, "label": label, "in": money_in, "out": money_out, "balance": bal})
    return render(request, "pos/ledger.html", {"rows": rows})


@admin_required
def expense_new(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Expense saved.")
        return redirect("pos:ledger")
    return render(request, "pos/crud_form.html",
                  {"form": form, "title": "Add expense", "back_url": reverse("pos:ledger")})
