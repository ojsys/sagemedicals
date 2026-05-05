from django import forms


class SmartSelectMixin:
    """
    Replace Django's default '-------' empty option with 'Select <Label>…'
    on every select field in the form.

    Works for:
    - ModelChoiceField (FK dropdowns) — sets empty_label
    - ChoiceField / TypedChoiceField — replaces the blank first choice in-place
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, "empty_label") and field.empty_label is not None:
                # ModelChoiceField / ModelMultipleChoiceField
                field.empty_label = f"Select {field.label}…"
            elif hasattr(field, "choices"):
                choices = list(field.choices)
                if (
                    choices
                    and str(choices[0][0]) == ""
                    and not str(choices[0][1]).replace("-", "").strip()
                ):
                    choices[0] = ("", f"Select {field.label}…")
                    field.choices = choices
