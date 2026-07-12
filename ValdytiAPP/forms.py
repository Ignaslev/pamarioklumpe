from django import forms

from .models import Worker


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ("first_name", "last_name", "job_title", "phone", "email", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

