from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Expense, Product, Sale, SaleItem, SaleReturn, Supplier, User


@admin.register(User)
class ShopUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Shop", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Shop", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "role", "is_active")


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "created_at", "cashier", "payment", "total", "is_void")
    inlines = [SaleItemInline]


admin.site.register([Product, Supplier, SaleReturn, Expense])
