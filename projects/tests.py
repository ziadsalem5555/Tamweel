from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from projects.models import (
    Category, Tag, Project, ProjectImage, Donation,
    Rating, Comment, ProjectReport, CommentReport
)

User = get_user_model()


class ProjectModelAndBusinessLogicTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            email='creator@example.com',
            password='Password123!',
            first_name='Omar',
            last_name='Sherif',
            mobile_phone='01011112222',
            is_active=True
        )
        self.donor1 = User.objects.create_user(
            email='donor1@example.com',
            password='Password123!',
            first_name='Laila',
            last_name='Murad',
            mobile_phone='01122223333',
            is_active=True
        )
        self.donor2 = User.objects.create_user(
            email='donor2@example.com',
            password='Password123!',
            first_name='Youssef',
            last_name='Chahine',
            mobile_phone='01233334444',
            is_active=True
        )

        self.category = Category.objects.create(name='Technology & AI', description='Tech projects')
        self.tag_tech = Tag.objects.create(name='tech')
        self.tag_cairo = Tag.objects.create(name='cairo')
        self.tag_health = Tag.objects.create(name='health')

        now = timezone.now()
        self.project = Project.objects.create(
            title='Cairo Tech Lab',
            details='A state-of-the-art innovation lab in Downtown Cairo.',
            category=self.category,
            creator=self.creator,
            total_target=Decimal('100000.00'),
            start_time=now - timezone.timedelta(days=1),
            end_time=now + timezone.timedelta(days=30),
            status='running'
        )
        self.project.tags.add(self.tag_tech, self.tag_cairo)

    def test_donation_and_progress_calculation(self):
        # Initial stats
        self.assertEqual(self.project.total_donations, Decimal('0.00'))
        self.assertEqual(self.project.donation_progress_percentage, 0.0)
        self.assertEqual(self.project.remaining_target, Decimal('100000.00'))

        # Add donation of 20,000 EGP (20%)
        Donation.objects.create(user=self.donor1, project=self.project, amount=Decimal('20000.00'))
        self.assertEqual(self.project.total_donations, Decimal('20000.00'))
        self.assertEqual(self.project.donation_progress_percentage, 20.0)
        self.assertEqual(self.project.remaining_target, Decimal('80000.00'))

        # Add donation of 30,000 EGP (total 50,000 = 50%)
        Donation.objects.create(user=self.donor2, project=self.project, amount=Decimal('30000.00'))
        self.assertEqual(self.project.total_donations, Decimal('50000.00'))
        self.assertEqual(self.project.donation_progress_percentage, 50.0)
        self.assertEqual(self.project.remaining_target, Decimal('50000.00'))

    def test_project_cancellation_25_percent_rule(self):
        """
        PDF Requirement: Project creator can cancel the project IF the donations are less than 25% of the target.
        """
        # Case 1: 10,000 EGP donations (10% < 25%) -> Cancellation allowed
        Donation.objects.create(user=self.donor1, project=self.project, amount=Decimal('10000.00'))
        self.assertTrue(self.project.can_be_cancelled, "Cancellation must be allowed when donations < 25%")

        # Attempt cancellation via creator
        self.client.force_login(self.creator)
        cancel_url = reverse('projects:project_cancel', kwargs={'pk': self.project.pk})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, 302)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'cancelled')

        # Reset status to running
        self.project.status = 'running'
        self.project.save()

        # Case 2: Add more donations to reach 26,000 EGP (26% > 25%) -> Cancellation forbidden
        Donation.objects.create(user=self.donor2, project=self.project, amount=Decimal('16000.00'))
        self.assertFalse(self.project.can_be_cancelled, "Cancellation must be forbidden when donations >= 25%")

        response_forbidden = self.client.post(cancel_url)
        self.assertEqual(response_forbidden.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'running', "Project status must remain running when cancellation rejected")

    def test_unauthorized_user_cannot_cancel(self):
        self.client.force_login(self.donor1)
        cancel_url = reverse('projects:project_cancel', kwargs={'pk': self.project.pk})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'running')

    def test_rating_and_average_calculation(self):
        # Donor 1 rates 5 stars
        Rating.objects.create(user=self.donor1, project=self.project, score=5)
        self.assertEqual(self.project.average_rating, 5.0)
        self.assertEqual(self.project.ratings_count, 1)

        # Donor 2 rates 4 stars -> Average (5 + 4)/2 = 4.5
        Rating.objects.create(user=self.donor2, project=self.project, score=4)
        self.assertEqual(self.project.average_rating, 4.5)
        self.assertEqual(self.project.ratings_count, 2)

        # Update donor 2 rating to 3 stars -> Average (5 + 3)/2 = 4.0
        Rating.objects.update_or_create(user=self.donor2, project=self.project, defaults={'score': 3})
        self.assertEqual(self.project.average_rating, 4.0)

    def test_comments_and_nested_replies(self):
        # Top level comment
        c1 = Comment.objects.create(
            user=self.donor1,
            project=self.project,
            content="Great project! When do you plan to open?"
        )
        self.assertFalse(c1.is_reply)

        # Reply to c1
        r1 = Comment.objects.create(
            user=self.creator,
            project=self.project,
            content="We plan to open within 3 months of funding!",
            parent=c1
        )
        self.assertTrue(r1.is_reply)
        self.assertEqual(c1.replies.count(), 1)
        self.assertEqual(c1.replies.first().content, r1.content)

    def test_project_and_comment_reports(self):
        # Report project
        p_report = ProjectReport.objects.create(
            reporter=self.donor1,
            project=self.project,
            reason="Inappropriate promotional content."
        )
        self.assertEqual(p_report.status, 'pending')

        # Report comment
        c = Comment.objects.create(user=self.donor2, project=self.project, content="Spam link here")
        c_report = CommentReport.objects.create(
            reporter=self.donor1,
            comment=c,
            reason="Spam content."
        )
        self.assertEqual(c_report.status, 'pending')

    def test_similar_projects_algorithm(self):
        """
        PDF Requirement: Project page should show 4 other similar projects based on project tags (fallback to category).
        """
        now = timezone.now()
        # Create 5 other projects with varying tags
        other_projects = []
        for i in range(5):
            p = Project.objects.create(
                title=f"Other Project {i}",
                details="Details",
                category=self.category,
                creator=self.creator,
                total_target=Decimal('50000.00'),
                start_time=now,
                end_time=now + timezone.timedelta(days=30),
                status='running'
            )
            other_projects.append(p)

        # Attach shared tag 'tech' to 2 projects
        other_projects[0].tags.add(self.tag_tech)
        other_projects[1].tags.add(self.tag_tech, self.tag_cairo)

        # Request project detail view
        detail_url = reverse('projects:project_detail', kwargs={'pk': self.project.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        similar_in_context = response.context['similar_projects']
        self.assertLessEqual(len(similar_in_context), 4)
        self.assertNotIn(self.project, similar_in_context, "Current project must not appear in similar projects")

    def test_search_by_title_and_tag(self):
        list_url = reverse('projects:project_list')

        # Search by Title
        resp_title = self.client.get(list_url, {'q': 'Cairo Tech'})
        self.assertEqual(resp_title.status_code, 200)
        self.assertContains(resp_title, 'Cairo Tech Lab')

        # Search by Tag
        resp_tag = self.client.get(list_url, {'q': 'tech'})
        self.assertEqual(resp_tag.status_code, 200)
        self.assertContains(resp_tag, 'Cairo Tech Lab')


from django.core.files.uploadedfile import SimpleUploadedFile

class ProjectImageManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            email='owner@example.com',
            password='Password123!',
            first_name='Owner',
            last_name='User',
            mobile_phone='01011110001',
            is_active=True
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='Password123!',
            first_name='Other',
            last_name='User',
            mobile_phone='01011110002',
            is_active=True
        )
        self.staff_user = User.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            mobile_phone='01011110003',
            is_staff=True,
            is_active=True
        )

        self.category = Category.objects.create(name='Education', description='Educational campaigns')
        now = timezone.now()
        self.project = Project.objects.create(
            title='Cairo Tech Hub',
            details='A hub for coding education in Cairo.',
            category=self.category,
            creator=self.owner,
            total_target=Decimal('50000.00'),
            start_time=now,
            end_time=now + timezone.timedelta(days=30),
            status='running'
        )

        # Create 3 test images using 1x1 transparent PNG bytes
        tiny_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
            b'\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        self.img1 = ProjectImage.objects.create(
            project=self.project,
            image=SimpleUploadedFile('test_img_a.png', tiny_png, content_type='image/png'),
            is_cover=True
        )
        self.img2 = ProjectImage.objects.create(
            project=self.project,
            image=SimpleUploadedFile('test_img_b.png', tiny_png, content_type='image/png'),
            is_cover=False
        )
        self.img3 = ProjectImage.objects.create(
            project=self.project,
            image=SimpleUploadedFile('test_img_c.png', tiny_png, content_type='image/png'),
            is_cover=False
        )

    def tearDown(self):
        # Clean up any leftover test files in storage
        for img in ProjectImage.objects.all():
            if img.image:
                try:
                    if img.image.storage.exists(img.image.name):
                        img.image.storage.delete(img.image.name)
                except Exception:
                    pass

    def test_owner_can_delete_individual_image(self):
        """
        Verify owner can delete a single image.
        DB record and physical file must be deleted.
        Other images and project details must remain intact.
        """
        self.client.force_login(self.owner)
        img2_path = self.img2.image.name
        storage = self.img2.image.storage
        self.assertTrue(storage.exists(img2_path), "Image 2 file must exist in storage initially")

        # Delete Image 2
        delete_url = reverse('projects:project_image_delete', kwargs={
            'project_id': self.project.pk,
            'image_id': self.img2.pk
        })
        response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['remaining_count'], 2)

        # Verify Image 2 deleted from DB and storage
        self.assertFalse(ProjectImage.objects.filter(pk=self.img2.pk).exists())
        self.assertFalse(storage.exists(img2_path), "Image 2 physical file must be deleted from storage")

        # Verify other images remain intact in DB and storage
        self.assertTrue(ProjectImage.objects.filter(pk=self.img1.pk).exists())
        self.assertTrue(ProjectImage.objects.filter(pk=self.img3.pk).exists())
        self.assertTrue(storage.exists(self.img1.image.name))
        self.assertTrue(storage.exists(self.img3.image.name))

        # Verify project itself remains untouched
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, 'Cairo Tech Hub')
        self.assertEqual(self.project.images.count(), 2)

    def test_cover_image_deletion_updates_cover_to_next_image(self):
        """
        When the cover image (img1) is deleted, next image (img2 or img3) becomes the cover.
        """
        self.client.force_login(self.owner)
        self.assertEqual(self.project.cover_image, self.img1.image.url)

        delete_url = reverse('projects:project_image_delete', kwargs={
            'project_id': self.project.pk,
            'image_id': self.img1.pk
        })
        response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        # Refresh from DB
        self.project.refresh_from_db()
        self.assertEqual(self.project.images.count(), 2)
        # Verify cover_image points to the next available image
        new_cover = self.project.images.filter(is_cover=True).first()
        self.assertIsNotNone(new_cover)
        self.assertEqual(self.project.cover_image, new_cover.image.url)

    def test_all_images_deleted_returns_none_for_cover(self):
        """
        When all images are deleted, cover_image returns None (triggering template placeholder).
        """
        self.client.force_login(self.owner)
        for img in [self.img1, self.img2, self.img3]:
            delete_url = reverse('projects:project_image_delete', kwargs={
                'project_id': self.project.pk,
                'image_id': img.pk
            })
            self.client.post(delete_url)

        self.project.refresh_from_db()
        self.assertEqual(self.project.images.count(), 0)
        self.assertIsNone(self.project.cover_image)

    def test_unauthorized_user_forbidden(self):
        """
        A non-owner user cannot delete campaign images -> receives 403 Forbidden.
        """
        self.client.force_login(self.other_user)
        delete_url = reverse('projects:project_image_delete', kwargs={
            'project_id': self.project.pk,
            'image_id': self.img1.pk
        })

        # Regular request
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403)

        # AJAX request
        ajax_response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(ajax_response.status_code, 403)

        # Verify image was NOT deleted
        self.assertTrue(ProjectImage.objects.filter(pk=self.img1.pk).exists())
        self.assertTrue(self.img1.image.storage.exists(self.img1.image.name))

    def test_mismatched_project_id_returns_404(self):
        """
        Attempting to delete an image with wrong project_id must return 404.
        """
        self.client.force_login(self.owner)
        delete_url = reverse('projects:project_image_delete', kwargs={
            'project_id': 99999,
            'image_id': self.img1.pk
        })
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 404)

    def test_upload_additional_images_on_edit_preserves_existing(self):
        """
        Uploading new images on edit appends them and does not wipe existing images.
        """
        self.client.force_login(self.owner)
        tiny_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
            b'\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        new_file = SimpleUploadedFile('new_photo.png', tiny_png, content_type='image/png')
        
        edit_url = reverse('projects:project_edit', kwargs={'pk': self.project.pk})
        response = self.client.post(edit_url, {
            'title': 'Cairo Tech Hub Updated',
            'details': 'Updated details for coding education.',
            'category': self.category.pk,
            'total_target': '60000.00',
            'start_time': self.project.start_time.strftime('%Y-%m-%dT%H:%M'),
            'end_time': self.project.end_time.strftime('%Y-%m-%dT%H:%M'),
            'tags_input': 'tech, education',
            'images': [new_file]
        })
        self.assertEqual(response.status_code, 302)

        self.project.refresh_from_db()
        self.assertEqual(self.project.title, 'Cairo Tech Hub Updated')
        # Total images must now be 4 (3 existing + 1 newly added)
        self.assertEqual(self.project.images.count(), 4)


class ProjectRatingUITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='rater@example.com',
            password='Password123!',
            first_name='Rater',
            last_name='Person',
            mobile_phone='01099998888',
            is_active=True
        )
        self.category = Category.objects.create(name='Social', description='Social campaigns')
        now = timezone.now()
        self.project = Project.objects.create(
            title='Cairo Community Garden',
            details='Creating a sustainable urban rooftop garden.',
            category=self.category,
            creator=self.user,
            total_target=Decimal('25000.00'),
            start_time=now,
            end_time=now + timezone.timedelta(days=30),
            status='running'
        )

    def test_authenticated_user_sees_tamweel_star_rating_component(self):
        self.client.force_login(self.user)
        detail_url = reverse('projects:project_detail', kwargs={'pk': self.project.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tamweel-star-rating')
        self.assertContains(response, 'star-rating-btn')
        self.assertContains(response, 'selected-rating-input')
        self.assertContains(response, 'Rate this campaign:')

    def test_submit_rating_and_updates_selected_state_and_average(self):
        self.client.force_login(self.user)
        rate_url = reverse('projects:rate_project', kwargs={'pk': self.project.pk})

        # Rate 4 stars
        resp = self.client.post(rate_url, {'score': '4'})
        self.assertEqual(resp.status_code, 302)

        # Check DB
        rating_obj = Rating.objects.get(user=self.user, project=self.project)
        self.assertEqual(rating_obj.score, 4)

        # Check detail page shows user rating and average
        detail_url = reverse('projects:project_detail', kwargs={'pk': self.project.pk})
        get_resp = self.client.get(detail_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Your rating:')
        self.assertEqual(self.project.average_rating, 4.0)

        # Update rating to 5 stars
        resp_update = self.client.post(rate_url, {'score': '5'})
        self.assertEqual(resp_update.status_code, 302)
        rating_obj.refresh_from_db()
        self.assertEqual(rating_obj.score, 5)
        self.assertEqual(self.project.average_rating, 5.0)

    def test_remove_rating_and_recalculates_average_and_allows_re_rating(self):
        # 1. Initially unrated: remove rating modal not shown
        self.client.force_login(self.user)
        detail_url = reverse('projects:project_detail', kwargs={'pk': self.project.pk})
        resp1 = self.client.get(detail_url)
        self.assertNotContains(resp1, 'removeRatingModal')

        # 2. Add second user with 4-star rating
        other_user = User.objects.create_user(
            email='other_rater@example.com',
            password='Password123!',
            first_name='Other',
            last_name='Rater',
            mobile_phone='01055554444',
            is_active=True
        )
        Rating.objects.create(user=other_user, project=self.project, score=4)

        # 3. User rates 2 stars -> Average = (4 + 2) / 2 = 3.0
        rate_url = reverse('projects:rate_project', kwargs={'pk': self.project.pk})
        self.client.post(rate_url, {'score': '2'})
        self.assertEqual(self.project.average_rating, 3.0)
        self.assertEqual(self.project.ratings_count, 2)

        # 4. Detail page now shows removeRatingModal & button
        resp2 = self.client.get(detail_url)
        self.assertContains(resp2, 'removeRatingModal')
        self.assertContains(resp2, 'Remove Rating')

        # 5. Remove rating
        remove_url = reverse('projects:remove_rating', kwargs={'pk': self.project.pk})
        resp_remove = self.client.post(remove_url)
        self.assertRedirects(resp_remove, detail_url)

        # 6. Check database & average recalculated from remaining rating only -> 4.0
        self.assertFalse(Rating.objects.filter(user=self.user, project=self.project).exists())
        self.assertEqual(self.project.average_rating, 4.0)
        self.assertEqual(self.project.ratings_count, 1)

        # 7. Detail page returns to unrated state
        resp3 = self.client.get(detail_url)
        self.assertNotContains(resp3, 'removeRatingModal')
        self.assertContains(resp3, 'Rate this campaign:')

        # 8. User can rate again -> rate 5 stars -> Average = (4 + 5) / 2 = 4.5
        self.client.post(rate_url, {'score': '5'})
        self.assertEqual(self.project.average_rating, 4.5)
        self.assertEqual(self.project.ratings_count, 2)
        self.assertTrue(Rating.objects.filter(user=self.user, project=self.project, score=5).exists())

    def test_unauthenticated_user_cannot_remove_rating(self):
        remove_url = reverse('projects:remove_rating', kwargs={'pk': self.project.pk})
        resp = self.client.post(remove_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), resp.get('Location'))


class CommentDeletionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(
            email='usera@example.com',
            password='Password123!',
            first_name='UserA',
            last_name='Owner',
            mobile_phone='01011110001',
            is_active=True
        )
        self.user_b = User.objects.create_user(
            email='userb@example.com',
            password='Password123!',
            first_name='UserB',
            last_name='Other',
            mobile_phone='01011110002',
            is_active=True
        )
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='Staff',
            mobile_phone='01011110003',
            is_active=True,
            is_staff=True
        )
        self.category = Category.objects.create(name='Tech', description='Tech projects')
        now = timezone.now()
        self.project = Project.objects.create(
            title='Clean Energy Generator',
            details='Solar and wind hybrid energy.',
            category=self.category,
            creator=self.user_a,
            total_target=Decimal('50000.00'),
            start_time=now,
            end_time=now + timezone.timedelta(days=30),
            status='running'
        )
        self.comment_a = Comment.objects.create(
            user=self.user_a,
            project=self.project,
            content='This is a comment from User A.'
        )
        self.reply_b = Comment.objects.create(
            user=self.user_b,
            project=self.project,
            content='Reply from User B.',
            parent=self.comment_a
        )

    def test_owner_sees_delete_action_in_ui(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'deleteCommentModal{self.comment_a.pk}')

    def test_non_owner_does_not_see_delete_action_in_ui(self):
        self.client.force_login(self.user_b)
        resp = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, f'deleteCommentModal{self.comment_a.pk}')

    def test_owner_can_delete_own_comment_and_cascades_replies(self):
        self.client.force_login(self.user_a)
        delete_url = reverse('projects:delete_comment', kwargs={'pk': self.project.pk, 'comment_id': self.comment_a.pk})
        resp = self.client.post(delete_url)
        self.assertRedirects(resp, reverse('projects:project_detail', kwargs={'pk': self.project.pk}))

        # Comment A deleted from DB
        self.assertFalse(Comment.objects.filter(pk=self.comment_a.pk).exists())
        # Reply B cascaded and deleted (no orphans)
        self.assertFalse(Comment.objects.filter(pk=self.reply_b.pk).exists())

    def test_owner_can_delete_own_reply_only(self):
        self.client.force_login(self.user_b)
        delete_url = reverse('projects:delete_comment', kwargs={'pk': self.project.pk, 'comment_id': self.reply_b.pk})
        resp = self.client.post(delete_url)
        self.assertRedirects(resp, reverse('projects:project_detail', kwargs={'pk': self.project.pk}))

        # Reply B deleted
        self.assertFalse(Comment.objects.filter(pk=self.reply_b.pk).exists())
        # Parent Comment A remains
        self.assertTrue(Comment.objects.filter(pk=self.comment_a.pk).exists())

    def test_unauthorized_user_cannot_delete_another_comment(self):
        self.client.force_login(self.user_b)
        delete_url = reverse('projects:delete_comment', kwargs={'pk': self.project.pk, 'comment_id': self.comment_a.pk})
        resp = self.client.post(delete_url)
        self.assertEqual(resp.status_code, 403, "Non-owner non-admin user must receive 403 Forbidden")
        self.assertTrue(Comment.objects.filter(pk=self.comment_a.pk).exists())

    def test_admin_can_delete_any_comment(self):
        self.client.force_login(self.admin_user)
        delete_url = reverse('projects:delete_comment', kwargs={'pk': self.project.pk, 'comment_id': self.comment_a.pk})
        resp = self.client.post(delete_url)
        self.assertRedirects(resp, reverse('projects:project_detail', kwargs={'pk': self.project.pk}))
        self.assertFalse(Comment.objects.filter(pk=self.comment_a.pk).exists())

    def test_unauthenticated_user_redirected_to_login(self):
        delete_url = reverse('projects:delete_comment', kwargs={'pk': self.project.pk, 'comment_id': self.comment_a.pk})
        resp = self.client.post(delete_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), resp.get('Location'))



