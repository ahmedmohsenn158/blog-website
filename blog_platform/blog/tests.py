from io import BytesIO
import tempfile
import shutil
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from blog.forms import RegisterForm, PostForm
from blog.models import Post, Category

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



