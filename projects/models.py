from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Avg, Sum
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('projects:category_projects', kwargs={'slug': self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.name}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('draft', 'Draft'),
    ]

    title = models.CharField(max_length=255)
    details = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='projects')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    total_target = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total fundraising target in EGP")
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    is_featured = models.BooleanField(default=False, help_text="Marked by admin to appear in featured projects slider/section")
    tags = models.ManyToManyField(Tag, related_name='projects', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})

    @property
    def total_donations(self):
        result = self.donations.aggregate(total=Sum('amount'))['total']
        return result if result is not None else Decimal('0.00')

    @property
    def donation_progress_percentage(self):
        if not self.total_target or self.total_target <= 0:
            return 0
        percentage = (self.total_donations / self.total_target) * Decimal('100')
        return round(float(percentage), 1)

    @property
    def remaining_target(self):
        rem = self.total_target - self.total_donations
        return max(Decimal('0.00'), rem)

    @property
    def is_target_reached(self):
        return self.total_donations >= self.total_target

    @property
    def average_rating(self):
        avg = self.ratings.aggregate(avg_score=Avg('score'))['avg_score']
        return round(avg, 1) if avg is not None else 0.0

    @property
    def ratings_count(self):
        return self.ratings.count()

    @property
    def can_be_cancelled(self):
        """
        PDF Rule: Project creator can cancel the project IF the donations are less than 25% of the target.
        """
        if self.status == 'cancelled':
            return False
        twenty_five_percent = self.total_target * Decimal('0.25')
        return self.total_donations < twenty_five_percent

    @property
    def is_expired(self):
        return timezone.now() > self.end_time

    @property
    def cover_image(self):
        cover = self.images.filter(is_cover=True).first()
        if not cover:
            cover = self.images.first()
        return cover.image.url if cover else None


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='projects/%Y/%m/')
    is_cover = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Project Image'
        verbose_name_plural = 'Project Images'
        ordering = ['-is_cover', 'id']

    def __str__(self):
        return f"Image for {self.project.title} (#{self.pk})"


class Donation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donations')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='donations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Donation'
        verbose_name_plural = 'Donations'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} donated {self.amount} EGP to {self.project.title}"


class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
        unique_together = ('user', 'project')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.get_full_name()} rated {self.project.title} - {self.score} Stars"


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.get_full_name()} on {self.project.title}"

    @property
    def is_reply(self):
        return self.parent is not None


class ProjectReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_reports')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Project Report'
        verbose_name_plural = 'Project Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report on {self.project.title} by {self.reporter.get_full_name()}"


class CommentReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_reports')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reports')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comment Report'
        verbose_name_plural = 'Comment Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report on Comment #{self.comment.pk} by {self.reporter.get_full_name()}"
