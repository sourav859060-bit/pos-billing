from django.urls import reverse

# (url name, label, url-name prefixes that highlight the link)
ADMIN_NAV = [
    ("pos:dashboard", "Dashboard", ("dashboard",)),
    ("pos:product_list", "Products", ("product",)),
    ("pos:staff_list", "Staff", ("staff",)),
    ("pos:supplier_list", "Suppliers", ("supplier",)),
    ("pos:sales", "Transactions", ("sales", "sale_")),
    ("pos:returns", "Returns", ("return",)),
    ("pos:ledger", "Ledger", ("ledger", "expense")),
    ("pos:billing", "Billing", ("billing",)),
]
STAFF_NAV = [
    ("pos:billing", "Billing", ("billing",)),
    ("pos:mine", "My sales", ("mine", "sale_")),
]


def nav(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    cur = request.resolver_match.url_name if request.resolver_match else ""
    items = ADMIN_NAV if user.is_shop_admin else STAFF_NAV
    return {"nav": [{"url": reverse(u), "label": l, "on": cur.startswith(p)} for u, l, p in items]}
