from io import BytesIO
import tempfile
import shutil
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from blog.forms import RegisterForm, PostForm, CommentForm
from blog.models import Post, Category, Comment

class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.post_list_url = reverse('post_list')

    def test_register_page_loads_correctly(self):
        """GET request to /register/ should display the form."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')
        self.assertIsInstance(response.context['form'], RegisterForm)

    def test_authenticated_user_redirected_from_register(self):
        """Logged-in users should be redirected away from /register/ to post_list."""
        user = User.objects.create_user(username='existinguser', email='existing@example.com', password='ComplexPassword123!')
        self.client.force_login(user)

        response = self.client.get(self.register_url)
        self.assertRedirects(response, self.post_list_url)

    def test_successful_registration(self):
        """A valid registration should create user, hash password, auto-login, and redirect."""
        payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePassword987!',
        }
        response = self.client.post(self.register_url, data=payload)

        # 1. Should redirect to post_list
        self.assertRedirects(response, self.post_list_url)

        # 2. User must exist in the database
        user = User.objects.filter(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'newuser@example.com')

        # 3. Password must be hashed (not plain text)
        self.assertTrue(user.check_password('SecurePassword987!'))
        self.assertNotEqual(user.password, 'SecurePassword987!')
        self.assertTrue(user.password.startswith('pbkdf2_'))

        # 4. User must be automatically logged in
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

        # 5. Success message should be queued
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Welcome to TheBlog, newuser!" in str(m) for m in messages))

    def test_registration_missing_fields(self):
        """Submitting empty data should fail and return form errors."""
        response = self.client.post(self.register_url, data={})
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('email', form.errors)
        self.assertIn('password', form.errors)

    def test_registration_duplicate_username(self):
        """Cannot register with a username that already exists (case-insensitive)."""
        User.objects.create_user(username='johndoe', email='john@example.com', password='Password123!')

        payload = {
            'username': 'JohnDoe',  # Testing case-insensitive uniqueness
            'email': 'different@example.com',
            'password': 'SecurePassword987!',
        }
        response = self.client.post(self.register_url, data=payload)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_registration_duplicate_email(self):
        """Cannot register with an email that already exists (case-insensitive)."""
        User.objects.create_user(username='firstuser', email='shared@example.com', password='Password123!')

        payload = {
            'username': 'seconduser',
            'email': 'SHARED@example.com',
            'password': 'SecurePassword987!',
        }
        response = self.client.post(self.register_url, data=payload)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn("An account with this email address already exists.", form.errors['email'])

    def test_registration_weak_password_too_short(self):
        """Password shorter than 8 characters should fail validation."""
        payload = {
            'username': 'validuser',
            'email': 'valid@example.com',
            'password': 'short',
        }
        response = self.client.post(self.register_url, data=payload)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_registration_password_entirely_numeric(self):
        """Password that is entirely numeric should fail validation."""
        payload = {
            'username': 'validuser',
            'email': 'valid@example.com',
            'password': '1234567890',
        }
        response = self.client.post(self.register_url, data=payload)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_registration_password_similar_to_username(self):
        """Password too similar to username should fail validation."""
        payload = {
            'username': 'alexander',
            'email': 'alexander@example.com',
            'password': 'alexanderpass',
        }
        response = self.client.post(self.register_url, data=payload)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)


MEDIA_DIR = tempfile.mkdtemp()

@override_settings(MEDIA_ROOT=MEDIA_DIR)
class PostCreationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='author1',
            email='author1@example.com',
            password='Password123!'
        )
        self.post_create_url = reverse('post_create')
        self.dashboard_url = reverse('dashboard')
        self.post_list_url = reverse('post_list')
        self.category, _ = Category.objects.get_or_create(name='Technology')

    def generate_test_image(self):
        file = BytesIO()
        image = Image.new('RGB', (100, 100), color='blue')
        image.save(file, 'JPEG')
        file.seek(0)
        return SimpleUploadedFile('test_featured.jpg', file.read(), content_type='image/jpeg')

    def test_post_create_login_required(self):
        """Unauthenticated users must be redirected to login page."""
        response = self.client.get(self.post_create_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_post_create_page_loads_for_authenticated_user(self):
        """Logged-in users should see the post creation form."""
        self.client.force_login(self.user)
        response = self.client.get(self.post_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_create.html')
        self.assertIsInstance(response.context['form'], PostForm)

    def test_create_post_success_as_draft(self):
        """Creating a post with is_published unchecked should save status as draft."""
        self.client.force_login(self.user)
        payload = {
            'title': 'My First Draft Post',
            'category': self.category.pk,
            'content': 'This is draft content.',
        }
        response = self.client.post(self.post_create_url, data=payload)
        self.assertRedirects(response, self.dashboard_url)

        post = Post.objects.filter(title='My First Draft Post').first()
        self.assertIsNotNone(post)
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.status, 'draft')
        self.assertFalse(post.is_published)
        self.assertEqual(post.category, self.category)

    def test_create_post_success_as_published(self):
        """Creating a post with is_published checked should save status as published."""
        self.client.force_login(self.user)
        payload = {
            'title': 'Published Community Post',
            'category': self.category.pk,
            'content': 'Published content for everyone.',
            'is_published': 'on',
        }
        response = self.client.post(self.post_create_url, data=payload)
        self.assertRedirects(response, self.dashboard_url)

        post = Post.objects.filter(title='Published Community Post').first()
        self.assertIsNotNone(post)
        self.assertEqual(post.status, 'published')
        self.assertTrue(post.is_published)

    def test_create_post_with_featured_image_bonus(self):
        """Should successfully upload and attach featured image to the created post."""
        self.client.force_login(self.user)
        image_file = self.generate_test_image()
        payload = {
            'title': 'Post With Featured Image',
            'category': self.category.pk,
            'content': 'Check out this awesome photo!',
            'featured_image': image_file,
            'is_published': 'on',
        }
        response = self.client.post(self.post_create_url, data=payload)
        self.assertRedirects(response, self.dashboard_url)

        post = Post.objects.filter(title='Post With Featured Image').first()
        self.assertIsNotNone(post)
        self.assertTrue(bool(post.featured_image))
        self.assertIn('test_featured', post.featured_image.name)

        # Verify the post list page renders the image url
        list_response = self.client.get(self.post_list_url)
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, post.featured_image.url)

    def test_create_post_validation_errors(self):
        """Missing title and content should return form validation errors."""
        self.client.force_login(self.user)
        response = self.client.post(self.post_create_url, data={})
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('content', form.errors)


class PostUpdateAndDeleteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username='postauthor',
            email='author@example.com',
            password='Password123!'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='Password123!'
        )
        self.category, _ = Category.objects.get_or_create(name='Tutorials')
        self.post = Post.objects.create(
            title='Initial Post Title',
            content='Initial post content.',
            author=self.author,
            category=self.category,
            status='draft'
        )
        self.edit_url = reverse('post_update', kwargs={'pk': self.post.pk})
        self.delete_url = reverse('post_delete', kwargs={'pk': self.post.pk})
        self.dashboard_url = reverse('dashboard')

    def test_post_update_page_loads_for_author(self):
        """Author can open the post edit page and it renders post_create.html with existing values."""
        self.client.force_login(self.author)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_create.html')
        self.assertTrue(response.context['is_edit'])
        self.assertEqual(response.context['form'].instance, self.post)
        self.assertContains(response, 'Initial Post Title')
        self.assertContains(response, 'Initial post content.')

    def test_post_update_login_required(self):
        """Unauthenticated user cannot access the edit page."""
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_post_update_forbidden_for_non_author(self):
        """Users other than the author receive 403 Forbidden when trying to edit."""
        self.client.force_login(self.other_user)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(self.edit_url, data={'title': 'Hacked Title', 'content': 'Hacked'})
        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Initial Post Title')

    def test_post_update_success(self):
        """Author can update post content, title, and status, with success message and redirect."""
        self.client.force_login(self.author)
        payload = {
            'title': 'Updated Post Title',
            'content': 'Updated content with new information.',
            'category': self.category.pk,
            'is_published': 'on',
        }
        response = self.client.post(self.edit_url, data=payload)
        self.assertRedirects(response, self.dashboard_url)

        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Updated Post Title')
        self.assertEqual(self.post.content, 'Updated content with new information.')
        self.assertEqual(self.post.status, 'published')
        self.assertTrue(self.post.is_published)

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Updated Post Title' in str(m) and 'updated successfully' in str(m) for m in messages))

    def test_post_delete_login_required(self):
        """Unauthenticated user cannot delete posts."""
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_post_delete_forbidden_for_non_author(self):
        """Non-author users cannot delete posts (403 Forbidden)."""
        self.client.force_login(self.other_user)
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_post_delete_success(self):
        """Author can delete their post, showing a success message and redirecting to dashboard."""
        self.client.force_login(self.author)
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, self.dashboard_url)

        # Post is deleted
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

        # Success message is set
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Initial Post Title' in str(m) and 'deleted successfully' in str(m) for m in messages))


class PostDetailAndCommentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username='postauthor',
            email='postauthor@example.com',
            password='Password123!'
        )
        self.user1 = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='Password123!'
        )
        self.user2 = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='Password123!'
        )
        self.category = Category.objects.create(name='Architecture')
        self.post = Post.objects.create(
            title='Understanding Modern Web Architecture',
            content='Modern web applications require clean separation of concerns and responsive design.',
            author=self.author,
            category=self.category,
            status='published'
        )
        self.draft_post = Post.objects.create(
            title='Top Secret Draft Article',
            content='Unreleased draft content.',
            author=self.author,
            category=self.category,
            status='draft'
        )
        self.comment1 = Comment.objects.create(
            post=self.post,
            author=self.user1,
            content='First insightful comment from Alice.'
        )
        self.comment2 = Comment.objects.create(
            post=self.post,
            author=self.author,
            content='Author response thanking Alice.'
        )
        self.post_detail_url = reverse('post_detail', kwargs={'pk': self.post.pk})
        self.draft_detail_url = reverse('post_detail', kwargs={'pk': self.draft_post.pk})

    def test_anonymous_user_can_view_published_post_without_comments(self):
        """Unauthenticated visitor can view the post, but comments are hidden and a lock prompt is shown."""
        response = self.client.get(self.post_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_detail.html')

        # Post content must be rendered
        self.assertContains(response, 'Understanding Modern Web Architecture')
        self.assertContains(response, 'Modern web applications require clean separation')

        # Comments must NOT be loaded or displayed in HTML
        self.assertIsNone(response.context['comments'])
        self.assertIsNone(response.context['comment_form'])
        self.assertNotContains(response, 'First insightful comment from Alice.')
        self.assertNotContains(response, 'Author response thanking Alice.')

        # Locked callout must be displayed with login and register links
        self.assertContains(response, 'Comments are restricted to members')
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('register'))

    def test_anonymous_user_cannot_post_comment(self):
        """Unauthenticated user submitting comment is redirected to login page without creating comment."""
        initial_count = Comment.objects.count()
        payload = {'content': 'Spam or unauthorized comment'}
        response = self.client.post(self.post_detail_url, data=payload)

        # Should redirect to login with next parameter
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        self.assertIn(f'next={self.post_detail_url}', response.url)
        self.assertEqual(Comment.objects.count(), initial_count)

    def test_authenticated_user_can_view_post_and_comments(self):
        """Signed-in user can view post details, all comments, and the comment form."""
        self.client.force_login(self.user1)
        response = self.client.get(self.post_detail_url)
        self.assertEqual(response.status_code, 200)

        # Context has comments and form
        self.assertIsNotNone(response.context['comments'])
        self.assertEqual(len(response.context['comments']), 2)
        self.assertIsInstance(response.context['comment_form'], CommentForm)

        # HTML displays comments
        self.assertContains(response, 'First insightful comment from Alice.')
        self.assertContains(response, 'Author response thanking Alice.')
        self.assertContains(response, 'Responding as')
        self.assertContains(response, 'Post comment')

        # Gated callout is not rendered
        self.assertNotContains(response, 'Comments are restricted to members')

    def test_authenticated_user_can_post_valid_comment(self):
        """Signed-in user can submit a comment successfully."""
        self.client.force_login(self.user2)
        payload = {'content': 'Bob comments: Great article! Loved the insights.'}
        response = self.client.post(self.post_detail_url, data=payload)

        self.assertRedirects(response, self.post_detail_url)

        new_comment = Comment.objects.filter(author=self.user2, post=self.post).first()
        self.assertIsNotNone(new_comment)
        self.assertEqual(new_comment.content, 'Bob comments: Great article! Loved the insights.')

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Your comment has been posted!' in str(m) for m in messages))

    def test_comment_empty_or_whitespace_rejected(self):
        """Submitting an empty or whitespace-only comment fails validation."""
        self.client.force_login(self.user1)
        initial_count = Comment.objects.count()
        payload = {'content': '    '}
        response = self.client.post(self.post_detail_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn('content', response.context['comment_form'].errors)
        self.assertEqual(Comment.objects.count(), initial_count)

    def test_comment_author_can_delete_their_comment(self):
        """The user who authored the comment can delete it."""
        self.client.force_login(self.user1)
        delete_url = reverse('comment_delete', kwargs={'pk': self.comment1.pk})
        response = self.client.post(delete_url)

        self.assertRedirects(response, self.post_detail_url)
        self.assertFalse(Comment.objects.filter(pk=self.comment1.pk).exists())

    def test_post_author_can_delete_comment_on_their_post(self):
        """The author of the post can delete any comment on their post."""
        self.client.force_login(self.author)
        delete_url = reverse('comment_delete', kwargs={'pk': self.comment1.pk})
        response = self.client.post(delete_url)

        self.assertRedirects(response, self.post_detail_url)
        self.assertFalse(Comment.objects.filter(pk=self.comment1.pk).exists())

    def test_unauthorized_user_cannot_delete_comment(self):
        """A user who is neither the comment author nor the post author cannot delete the comment (403)."""
        self.client.force_login(self.user2)
        delete_url = reverse('comment_delete', kwargs={'pk': self.comment1.pk})
        response = self.client.post(delete_url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=self.comment1.pk).exists())

    def test_draft_post_detail_access_control(self):
        """Author can view draft post detail, but other users and anonymous visitors get 404."""
        # 1. Author can access draft
        self.client.force_login(self.author)
        response = self.client.get(self.draft_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top Secret Draft Article')

        # 2. Another authenticated user gets 404
        self.client.force_login(self.user1)
        response = self.client.get(self.draft_detail_url)
        self.assertEqual(response.status_code, 404)

        # 3. Anonymous visitor gets 404
        self.client.logout()
        response = self.client.get(self.draft_detail_url)
        self.assertEqual(response.status_code, 404)



