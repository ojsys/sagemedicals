from django import forms
from django.core.exceptions import ValidationError

from core.forms import SmartSelectMixin
from patients.models import Allergy, ChronicCondition, NextOfKin, Patient
from patients.services import validate_nigerian_phone


class PatientRegistrationForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            # Identity
            "first_name", "middle_name", "last_name", "date_of_birth",
            "sex", "gender_identity", "marital_status", "occupation",
            "religion", "ethnicity", "state_of_origin", "lga_of_origin",
            "preferred_language", "blood_group",
            # Contact
            "phone", "phone_alt", "email", "address", "address_state", "address_lga",
            # Payer
            "payer_type", "nhia_number", "hmo_name", "hmo_number", "hmo_plan", "corporate_employer",
            # Media
            "photo", "id_document", "hmo_card",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "gender_identity": forms.TextInput(attrs={"placeholder": "Optional — patient's own description"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "nhia_number": forms.TextInput(attrs={"placeholder": "e.g. SHA/00123456/A"}),
            "hmo_name": forms.TextInput(attrs={"placeholder": "e.g. Hygeia HMO, Leadway Health"}),
            "hmo_plan": forms.TextInput(attrs={"placeholder": "e.g. Basic, Standard, Executive"}),
            "hmo_number": forms.TextInput(attrs={"placeholder": "Member / policy number"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput)):
                field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
        # Required overrides
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["date_of_birth"].required = True
        self.fields["sex"].required = True
        self.fields["phone"].required = True
        self.fields["payer_type"].required = True

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if phone:
            try:
                return validate_nigerian_phone(phone)
            except ValueError as exc:
                raise ValidationError(str(exc))
        return phone

    def clean_phone_alt(self):
        phone = self.cleaned_data.get("phone_alt", "")
        if phone:
            try:
                return validate_nigerian_phone(phone)
            except ValueError as exc:
                raise ValidationError(str(exc))
        return phone

    def clean(self):
        cleaned = super().clean()
        payer = cleaned.get("payer_type")
        if payer == "nhia" and not cleaned.get("nhia_number"):
            self.add_error("nhia_number", "NHIA enrollee ID is required for NHIA payers.")
        if payer in ("private_hmo",) and not cleaned.get("hmo_name"):
            self.add_error("hmo_name", "HMO name is required.")
        if payer == "corporate" and not cleaned.get("corporate_employer"):
            self.add_error("corporate_employer", "Employer name is required for corporate billing.")
        return cleaned


class NextOfKinForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = NextOfKin
        fields = ["full_name", "relationship", "phone", "phone_alt", "address"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if phone:
            try:
                return validate_nigerian_phone(phone)
            except ValueError as exc:
                raise ValidationError(str(exc))
        return phone

    def clean_phone_alt(self):
        phone = self.cleaned_data.get("phone_alt", "")
        if phone:
            try:
                return validate_nigerian_phone(phone)
            except ValueError as exc:
                raise ValidationError(str(exc))
        return phone


class AllergyForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = Allergy
        fields = ["allergen", "allergy_type", "severity", "reaction", "date_recorded"]
        widgets = {
            "date_recorded": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "reaction": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif not isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", "form-control")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class ChronicConditionForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = ChronicCondition
        fields = ["icd10_code", "description", "status", "onset_date", "notes"]
        widgets = {
            "onset_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif not isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", "form-control")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class PatientSearchForm(forms.Form):
    q = forms.CharField(
        label="Search",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Name, hospital number, phone, or NHIA number…",
            "autofocus": True,
            "hx-get": "/patients/search/",
            "hx-target": "#search-results",
            "hx-trigger": "keyup changed delay:300ms",
            "hx-indicator": "#search-spinner",
        }),
    )
