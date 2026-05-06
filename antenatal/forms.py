from datetime import date

from django import forms

from core.forms import SmartSelectMixin
from .models import ANCRecord, ANCVisit, ObstetricScan

BLOOD_GROUP_CHOICES = [
    ("", "Select blood group…"),
    ("A",  "A"),
    ("B",  "B"),
    ("AB", "AB"),
    ("O",  "O"),
]


class ANCRecordForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = ANCRecord
        fields = [
            "lmp", "edd", "gravida", "para",
            "blood_group", "rhesus", "booking_date", "is_active", "notes",
        ]
        widgets = {
            "lmp":          forms.DateInput(attrs={"type": "date"}),
            "edd":          forms.DateInput(attrs={"type": "date"}),
            "booking_date": forms.DateInput(attrs={"type": "date"}),
            "notes":        forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                continue
            if isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")

        self.fields["edd"].required = True
        self.fields["blood_group"].widget.choices = BLOOD_GROUP_CHOICES

    def clean(self):
        cleaned = super().clean()
        lmp = cleaned.get("lmp")
        edd = cleaned.get("edd")
        if lmp and edd and lmp >= edd:
            self.add_error("lmp", "LMP must be before the expected delivery date.")
        return cleaned


class ANCVisitForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = ANCVisit
        fields = [
            "visit_date", "gestational_age_weeks",
            "weight_kg", "bp_systolic", "bp_diastolic",
            "fundal_height_cm", "fetal_heart_rate", "presentation",
            "urine_protein", "urine_glucose",
            "next_visit_date", "diagnosis", "plan", "notes",
        ]
        widgets = {
            "visit_date":      forms.DateInput(attrs={"type": "date"}),
            "next_visit_date": forms.DateInput(attrs={"type": "date"}),
            "diagnosis":       forms.Textarea(attrs={"rows": 3}),
            "plan":            forms.Textarea(attrs={"rows": 3}),
            "notes":           forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")

        self.fields["visit_date"].initial = date.today()
        self.fields["visit_date"].required = True
        self.fields["gestational_age_weeks"].required = True

    def clean(self):
        cleaned = super().clean()
        sys = cleaned.get("bp_systolic")
        dia = cleaned.get("bp_diastolic")
        if (sys and not dia) or (dia and not sys):
            msg = "Both systolic and diastolic values are required."
            if not sys:
                self.add_error("bp_systolic", msg)
            else:
                self.add_error("bp_diastolic", msg)
        return cleaned


class ObstetricScanForm(SmartSelectMixin, forms.ModelForm):
    class Meta:
        model = ObstetricScan
        fields = [
            "scan_date", "gestational_age_weeks", "gestational_age_days",
            "placenta_location", "amniotic_fluid",
            "findings", "impression", "report_file",
        ]
        widgets = {
            "scan_date":  forms.DateInput(attrs={"type": "date"}),
            "findings":   forms.Textarea(attrs={"rows": 3}),
            "impression": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.Select, forms.ClearableFileInput)):
                w.attrs.setdefault("class", "form-select" if isinstance(w, forms.Select) else "form-control")
            else:
                w.attrs.setdefault("class", "form-control")

        self.fields["scan_date"].initial = date.today()
        self.fields["scan_date"].required = True
