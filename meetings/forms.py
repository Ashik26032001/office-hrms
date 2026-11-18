from django import forms
from django.utils import timezone
from .models import Meeting
from employees.models import Employee


class MeetingForm(forms.ModelForm):
    attendees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(status='active').select_related('user'),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label='Invite Employees',
    )

    class Meta:
        model  = Meeting
        fields = [
            'title', 'meeting_type', 'description', 'agenda',
            'scheduled_at', 'duration_mins',
            'meeting_link', 'location',
            'attendees',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Q4 Sprint Planning',
            }),
            'meeting_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Brief description of the meeting purpose…',
            }),
            'agenda': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': '1. Welcome & Introductions\n2. Project status update\n3. Q&A',
            }),
            'scheduled_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'duration_mins': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 5, 'max': 480,
            }),
            'meeting_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://meet.google.com/xxx  or  https://zoom.us/j/xxx',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Conference Room A  or  Remote',
            }),
        }

    def clean_scheduled_at(self):
        dt = self.cleaned_data.get('scheduled_at')
        if dt and dt <= timezone.now():
            raise forms.ValidationError('Meeting must be scheduled in the future.')
        return dt

    def clean_attendees(self):
        attendees = self.cleaned_data.get('attendees')
        if not attendees:
            raise forms.ValidationError('Select at least one employee.')
        return attendees


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = 'datetime-local'
