from django.core.management.base import BaseCommand

from pos.models import Product, Supplier, User


class Command(BaseCommand):
    help = "Create the demo users, suppliers and products from the original HTML app."

    def handle(self, *args, **opts):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_user("admin", password="admin123", first_name="Admin", role="admin",
                                     is_staff=True, is_superuser=True)
        if not User.objects.filter(username="staff").exists():
            User.objects.create_user("staff", password="staff123", first_name="Anita", role="staff")

        surat, _ = Supplier.objects.get_or_create(name="Surat Silks", defaults={"phone": "9876500001", "city": "Surat", "due": 12000})
        erode, _ = Supplier.objects.get_or_create(name="Erode Cottons", defaults={"phone": "9876500002", "city": "Erode", "due": 0})

        rows = [("Cotton Shirt", "SH-101", "Shirts", 799, 40), ("Silk Saree", "SR-201", "Sarees", 3499, 12),
                ("Denim Jeans", "JN-301", "Bottoms", 1299, 25), ("Linen Kurta", "KR-401", "Kurtas", 999, 4),
                ("Cotton Dhoti", "DH-501", "Dhotis", 449, 60), ("Bath Towel", "TW-601", "Home", 299, 30)]
        for i, (name, sku, cat, price, stock) in enumerate(rows):
            Product.objects.get_or_create(sku=sku, defaults={
                "name": name, "category": cat, "price": price, "stock": stock,
                "supplier": surat if i % 2 else erode})
        self.stdout.write(self.style.SUCCESS("Demo data ready: admin/admin123, staff/staff123"))
