from decimal import Decimal

from django import forms
from django.utils import timezone

from accounts.models import Role, User
from core.forms import SmartSelectMixin

from .models import BirthRecord

# Staff who can be recorded as having delivered the baby (midwives are nurses).
ATTENDING_ROLES = [Role.DOCTOR, Role.RESIDENT, Role.NURSE, Role.CHEW]


class AttendingClinicianField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.display_name} · {obj.get_role_display()}"


class BirthRecordForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = BirthRecord
        fields = [
            "child_first_name", "child_middle_name", "child_surname", "sex",
            "date_of_birth", "time_of_birth", "weight_kg", "length_cm",
            "gestational_age_weeks", "delivery_mode",
            "birth_order", "babies_in_delivery",
            "father_name", "attended_by", "notes",
        ]
        field_classes = {"attended_by": AttendingClinicianField}
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "time_of_birth": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "weight_kg":     forms.NumberInput(attrs={"step": "0.01", "min": "0.2", "max": "7", "placeholder": "e.g. 3.20"}),
            "length_cm":     forms.NumberInput(attrs={"step": "0.1", "placeholder": "e.g. 50.0"}),
            "notes":         forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")

        attending = User.objects.filter(is_active=True, role__in=ATTENDING_ROLES)
        if self.instance.attended_by_id:
            # Keep the original attendant selectable even if they've since left.
            attending = attending | User.objects.filter(pk=self.instance.attended_by_id)
        self.fields["attended_by"].queryset = attending.order_by("first_name", "last_name")
        self.fields["date_of_birth"].initial = timezone.localdate()

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean_weight_kg(self):
        weight = self.cleaned_data["weight_kg"]
        if not Decimal("0.2") <= weight <= Decimal("7"):
            raise forms.ValidationError("Enter a birth weight between 0.2 kg and 7 kg.")
        return weight

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("birth_order")
        count = cleaned.get("babies_in_delivery")
        if order is not None and count is not None:
            if order < 1 or count < 1:
                self.add_error("birth_order", "Birth order and number of babies must be at least 1.")
            elif order > count:
                self.add_error("birth_order", "Birth order cannot exceed the number of babies delivered.")
        return cleaned
