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
