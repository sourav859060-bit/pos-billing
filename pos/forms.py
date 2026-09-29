from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Expense, Product, Supplier, User


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "category", "price", "stock", "supplier"]


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "phone", "city", "due"]


class StaffForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False),
                               help_text="Leave blank to keep the current password.")

    class Meta:
        model = User
        fields = ["first_name", "username", "role", "is_active"]
        labels = {"first_name": "Name", "is_active": "Active"}

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if not self.instance.pk and not pw:
            raise forms.ValidationError("A password is required for a new account.")
        if pw:
            validate_password(pw, self.instance)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)      # stored hashed, unlike the old plain-text pass
        if commit:
            user.save()
        return user


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "note", "amount"]
