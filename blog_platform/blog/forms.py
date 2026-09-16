from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Post, Category, Comment

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'autocomplete': 'new-password'
        }),
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

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            user = User(
                username=self.cleaned_data.get('username', ''),
                email=self.cleaned_data.get('email', '')
            )
            validate_password(password, user=user)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        # Cryptographic password hashing (Django default PBKDF2/Argon2)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class PostForm(forms.ModelForm):
    is_published = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox-input'})
    )

    class Meta:
        model = Post
        fields = ('title', 'category', 'content', 'featured_image')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'editor-input',
                'placeholder': 'A clear, specific title',
                'autofocus': True
            }),
            'category': forms.Select(attrs={
                'class': 'editor-select'
            }),
            'content': forms.Textarea(attrs={
                'class': 'editor-textarea',
                'placeholder': 'Write your post...'
            }),
            'featured_image': forms.ClearableFileInput(attrs={
                'class': 'editor-input editor-file-input',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['content'].required = True
        self.fields['category'].required = False
        self.fields['category'].empty_label = "Select a category (optional)"
        self.fields['featured_image'].required = False
        if self.instance and self.instance.pk:
            self.fields['is_published'].initial = self.instance.status == 'published'

    def save(self, commit=True):
        post = super().save(commit=False)
        is_published = self.cleaned_data.get('is_published', False)
        post.status = 'published' if is_published else 'draft'
        if commit:
            post.save()
        return post


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'comment-textarea',
                'placeholder': 'Share your thoughts, ask questions, or contribute to the discussion...',
                'rows': 3,
                'aria-label': 'Write a comment',
                'required': True,
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Comment cannot be empty.")
        return content