from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'autocomplete': 'new-password'
        }),
        validators=[validate_password],
        help_text="Your password must contain at least 8 characters."
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'autocomplete': 'username',
                'autofocus': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'autocomplete': 'email'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Cryptographic password hashing (Django default PBKDF2/Argon2)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user