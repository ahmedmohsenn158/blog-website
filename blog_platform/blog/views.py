from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.urls import reverse
from .forms import RegisterForm, PostForm, CommentForm
from .models import Post, Category, Comment

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


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, f'Post "{post.title}" created successfully!')
            return redirect('dashboard')
    else:
        form = PostForm()

    return render(request, 'post_create.html', {'form': form})


@login_required
def dashboard_view(request):
    posts = Post.objects.filter(author=request.user).select_related('category')
    draft_count = posts.filter(status='draft').count()
    context = {
        'posts': posts,
        'draft_count': draft_count,
    }
    return render(request, 'dashboard.html', context)


def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('author', 'category'), pk=pk)

    # Draft visibility: only the post author can view draft posts
    if post.status == 'draft' and request.user != post.author:
        raise Http404("Post not found.")

    comments = None
    comment_form = None

    if request.user.is_authenticated:
        if request.method == 'POST':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.post = post
                comment.author = request.user
                comment.save()
                messages.success(request, "Your comment has been posted!")
                return redirect('post_detail', pk=post.pk)
        else:
            comment_form = CommentForm()

        comments = post.comments.select_related('author').all()
    else:
        # If an unauthenticated user attempts to POST a comment, redirect to login
        if request.method == 'POST':
            messages.info(request, "Please log in to leave a comment.")
            return redirect(f"{reverse('login')}?next={request.path}")

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
    }
    return render(request, 'post_detail.html', context)


@login_required
def post_update(request, pk):
    post = get_object_or_404(Post, pk=pk)

    # Server-side ownership authorization check
    if post.author != request.user:
        raise PermissionDenied("You do not have permission to edit this post.")

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated_post = form.save()
            messages.success(request, f'Post "{updated_post.title}" was updated successfully!')
            return redirect('dashboard')
    else:
        form = PostForm(instance=post)

    context = {
        'form': form,
        'is_edit': True,
        'post': post,
    }
    return render(request, 'post_create.html', context)


@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)

    # Server-side ownership authorization check
    if post.author != request.user:
        raise PermissionDenied("You do not have permission to delete this post.")

    if request.method == 'POST':
        title = post.title
        post.delete()
        messages.success(request, f'Post "{title}" was deleted successfully.')
        return redirect('dashboard')

    # If accessed via GET, redirect back to dashboard
    return redirect('dashboard')


@login_required
def comment_delete(request, pk):
    comment = get_object_or_404(Comment.objects.select_related('post'), pk=pk)

    # Authorization: only the comment author or the post author can delete the comment
    if request.user != comment.author and request.user != comment.post.author:
        raise PermissionDenied("You do not have permission to delete this comment.")

    post_pk = comment.post.pk
    if request.method == 'POST':
        comment.delete()
        messages.success(request, "Comment deleted successfully.")

    return redirect('post_detail', pk=post_pk)



