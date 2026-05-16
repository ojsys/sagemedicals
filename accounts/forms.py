from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.forms import SmartSelectMixin

from .models import Role, User


# Roles a non-superuser staff manager (Lead Doctor) may assign.
# We deliberately exclude SUPER_ADMIN — only an actual platform superuser can create one.
_RESTRICTED_ROLES_FOR_LEAD = [
    Role.SUPER_ADMIN,
]


class StaffUserCreateForm(SmartSelectMixin, forms.ModelForm):
    """Create a new staff user from the application — used by Super Admin / Lead Doctor."""

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        help_text="At least 8 characters. Mix letters, numbers and a symbol.",
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "department",
            "is_active",
        )

    def __init__(self, *args, requesting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requesting_user = requesting_user
        # Lead Doctors cannot create Super Admins
        if requesting_user is not None and not requesting_user.is_superuser:
            role_field = self.fields["role"]
            role_field.choices = [
                (val, label) for val, label in role_field.choices
                if val not in _RESTRICTED_ROLES_FOR_LEAD
            ]
        self.fields["is_active"].initial = True

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error("password1", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        # Hospital staff need is_staff so they can use the application properly.
        # The Django-admin "is_staff" flag is separately controlled in the Django admin.
        if commit:
            user.save()
        return user


class StaffUserUpdateForm(SmartSelectMixin, forms.ModelForm):
    """Edit basic profile + role/active state for an existing staff user."""

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "department",
            "is_active",
        )

    def __init__(self, *args, requesting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requesting_user = requesting_user
        if requesting_user is not None and not requesting_user.is_superuser:
            role_field = self.fields["role"]
            role_field.choices = [
                (val, label) for val, label in role_field.choices
                if val not in _RESTRICTED_ROLES_FOR_LEAD
            ]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Another user already uses this email.")
        return email


class PasswordResetForm(forms.Form):
    password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error("password1", e)
        return cleaned
