from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponse
from .forms import RegisterForm

def register_view(request):
    # If already logged in, redirect straight to posts
    if request.user.is_authenticated:
        return redirect('post_list')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto-login after registration
            messages.success(request, f"Welcome to TheBlog, {user.username}! Your account has been created.")
            return redirect('post_list')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})

def post_list_view(request):
    return HttpResponse("<h1>Posts</h1><p>Post list coming soon.</p>")

def dashboard_view(request):
    return HttpResponse("<h1>Dashboard</h1><p>Dashboard coming soon.</p>")