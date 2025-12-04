from django.shortcuts import render
from django import forms
from .models import Book, Reader, Issue,Admin
from django import forms
class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['name', 'isbn', 'image', 'author', 'category', 'number_in_stock', 'description', 'rating', 'status']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'type': 'number',
                'min': '1.0',
                'max': '5.0',
                'step': '0.1',
                'placeholder': 'Enter rating (1.0 - 5.0)',
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={'class': 'form-control'})
        }

# def view_books(request):
#     books = Book.objects.all()  # fetch all books
#     return render(request, 'view_books.html', {'books': books})

class ReaderForm(forms.ModelForm):
    class Meta:
        model = Reader
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address', 'is_staff_member']
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'type': 'tel',
                'pattern': '[0-9]{10}',
                'maxlength': '10',
                'placeholder': '10 digit phone number',
            }),
        }

class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['reader', 'book', 'due_date']   

class ReaderRegisterForm(forms.ModelForm):
    ROLE_CHOICES = (
        (False, 'Student'),
        (True, 'Staff / Teacher'),
    )

    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Confirm Password')
    is_staff_member = forms.TypedChoiceField(
        choices=ROLE_CHOICES,
        coerce=lambda x: x in (True, 'True'),
        widget=forms.RadioSelect,
        label='Role',
        initial=False,
        help_text='Select whether you are a student or staff/teacher.'
    )

    class Meta:
        model = Reader
        fields = ['reader_id', 'name', 'date_of_birth', 'phone_number', 'address', 'is_staff_member']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'format': '%Y-%m-%d',
                'placeholder': 'YYYY-MM-DD',
            }),
            'address': forms.Textarea(attrs={
                'rows': 3,
                'cols': 40,
            }),
            'phone_number': forms.TextInput(attrs={
                'type': 'tel',
                'pattern': '[0-9]{10}',
                'maxlength': '10',
                'placeholder': '10 digit phone number',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing_class} sl-input w-full rounded-lg border border-slate-200 px-3 py-2 text-sm".strip()
            if not field.widget.attrs.get('placeholder') and field.widget.__class__.__name__ not in ('RadioSelect',):
                field.widget.attrs['placeholder'] = field.label

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        phone_number = cleaned_data.get('phone_number')
        
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
        
        if phone_number:
            if not phone_number.isdigit() or len(phone_number) != 10:
                raise forms.ValidationError({'phone_number': 'Phone number must be exactly 10 digits.'})
        
        return cleaned_data


class AdminRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Admin
        fields = ['admin_id', 'name', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} sl-input w-full rounded-lg border border-slate-200 px-3 py-2 text-sm".strip()
            if not field.widget.attrs.get('placeholder'):
                field.widget.attrs['placeholder'] = field.label
class ReaderEditProfileForm(forms.ModelForm):
    class Meta:
        model = Reader
        fields = ['name', 'date_of_birth', 'phone_number', 'address', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'format': '%Y-%m-%d',
                'placeholder': 'YYYY-MM-DD',
            }),
            'address': forms.Textarea(attrs={
                'rows': 4,
                'cols': 40,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing_class} sl-input w-full rounded-lg border border-slate-200 px-3 py-2 text-sm".strip()
            if not field.widget.attrs.get('placeholder') and field.widget.__class__.__name__ not in ('RadioSelect', 'Textarea'):
                field.widget.attrs['placeholder'] = field.label

class AdminEditProfileForm(forms.ModelForm):
    class Meta:
        model = Admin
        fields = ['name', 'profile_picture']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing_class} sl-input w-full rounded-lg border border-slate-200 px-3 py-2 text-sm".strip()
            if not field.widget.attrs.get('placeholder'):
                field.widget.attrs['placeholder'] = field.label

class UploadExcelForm(forms.Form):
    excel_file = forms.FileField(
        label="Upload Excel (.xlsx)",
        help_text="Upload an Excel file containing book data."
    )

    def clean_excel_file(self):
        uploaded = self.cleaned_data.get("excel_file")

        if uploaded:
            name = uploaded.name.lower()
            if not name.endswith(".xlsx"):
                raise forms.ValidationError("Only .xlsx files are supported.")

            max_size = 10 * 1024 * 1024  # 10 MB
            if uploaded.size > max_size:
                raise forms.ValidationError("File too large (max 10 MB).")

        return uploaded
