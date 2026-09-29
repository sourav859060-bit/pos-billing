from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models

GST_RATE = Decimal("0.05")
LOW_STOCK = 5


def money(d):
    return Decimal(d).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class User(AbstractUser):
    """Replaces the old `staff` list. Password hashing, login and the
    active yes/no flag (is_active) now come from Django itself."""
    ADMIN, STAFF = "admin", "staff"
    ROLES = [(STAFF, "Staff"), (ADMIN, "Admin")]
    role = models.CharField(max_length=10, choices=ROLES, default=STAFF)

    class Meta:
        ordering = ["username"]

    @property
    def is_shop_admin(self):
        return self.role == self.ADMIN or self.is_superuser

    @property
    def role_label(self):
        return "admin" if self.is_shop_admin else "staff"

    def display_name(self):
        return self.get_full_name() or self.username


class Supplier(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    due = models.DecimalField("Amount due", max_digits=12, decimal_places=2, default=0,
                              validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField("SKU", max_length=40, unique=True)
    category = models.CharField(max_length=80, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="products")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Sale(models.Model):
    PAYMENTS = [("Cash", "Cash"), ("Card", "Card"), ("UPI", "UPI")]

    invoice_no = models.CharField(max_length=12, unique=True, null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cashier = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="sales")
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    payment = models.CharField(max_length=10, choices=PAYMENTS, default="Cash")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    is_void = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.invoice_no or f"Sale #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.invoice_no:
            self.invoice_no = f"INV{self.pk:04d}"
            super().save(update_fields=["invoice_no"])

    @staticmethod
    def totals(subtotal, disc_pct):
        """Same maths as the old calc(): discount first, then 5% GST on the rest."""
        dv = money(subtotal * disc_pct / 100)
        tax = money((subtotal - dv) * GST_RATE)
        return dv, tax, subtotal - dv + tax


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, related_name="+")
    name = models.CharField(max_length=120)          # snapshot, survives product edits/deletes
    price = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.PositiveIntegerField()
    returned_qty = models.PositiveIntegerField(default=0)

    @property
    def returnable(self):
        return self.qty - self.returned_qty

    @property
    def line_total(self):
        return self.qty * self.price


class SaleReturn(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="returns")
    item_name = models.CharField(max_length=120)
    qty = models.PositiveIntegerField()
    refund = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=200, default="-")

    class Meta:
        ordering = ["-created_at", "-id"]


class Expense(models.Model):
    CATEGORIES = [(c, c) for c in ("Purchase", "Rent", "Salary", "Other")]
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField("Type", max_length=20, choices=CATEGORIES, default="Purchase")
    note = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["-created_at", "-id"]
