from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from .forms import RegisterForm
from .models import Post, Category

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

def post_list(request):
    # Base queryset: only published posts
    queryset = Post.objects.filter(status='published').select_related('author', 'category')

    # 1. Search by title
    search_query = request.GET.get('q', '').strip()
    if search_query:
        queryset = queryset.filter(title__icontains=search_query)

    # 2. Filter by category name
    category_name = request.GET.get('category', '').strip()
    if category_name:
        queryset = queryset.filter(category__name=category_name)

    # 3. Sort ordering
    sort_order = request.GET.get('sort', 'newest')
    if sort_order == 'oldest':
        queryset = queryset.order_by('created_at')
    else:
        queryset = queryset.order_by('-created_at')

    # 4. Pagination (e.g., 6 posts per page)
    paginator = Paginator(queryset, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Fetch all categories that exist
    categories = Category.objects.values_list('name', flat=True)

    context = {
        'posts': page_obj,  # Django allows iterating directly over page_obj as posts
        'page_obj': page_obj,
        'paginator': paginator,
        'categories': categories,
    }
    return render(request, 'post_list.html', context)


def post_create(request):
    return HttpResponse("<h1>Create Post</h1><p>Coming soon.</p>")

def dashboard_view(request):
    return HttpResponse("<h1>Dashboard</h1><p>Dashboard coming soon.</p>")

