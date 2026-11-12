from django import forms
from django.contrib.auth.hashers import make_password
from accounts.models import CustomUser
from .models import Employee, Department, Shift


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['name', 'start_time', 'end_time', 'grace_period_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'grace_period_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EmployeeCreateForm(forms.Form):
    # User fields
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Min 8 characters"
    )

    # Employee fields
    employee_id = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Department"
    )
    shift = forms.ModelChoiceField(
        queryset=Shift.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Shift"
    )
    designation = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    joining_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_employee_id(self):
        emp_id = self.cleaned_data['employee_id']
        if Employee.objects.filter(employee_id=emp_id).exists():
            raise forms.ValidationError("This Employee ID already exists.")
        return emp_id


class EmployeeEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Employee
        fields = ['employee_id', 'department', 'shift', 'designation', 'joining_date', 'status', 'photo']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
