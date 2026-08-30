from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Sum, Count
from django.utils import timezone
from django.utils.text import slugify
from django.http import HttpResponseForbidden, JsonResponse
from django.core.exceptions import PermissionDenied

from .models import (
    Project, Category, Tag, ProjectImage, Donation,
    Rating, Comment, ProjectReport, CommentReport
)
from .forms import (
    ProjectForm, DonationForm, CommentForm, RatingForm,
    ProjectReportForm, CommentReportForm
)


def home_view(request):
    """
    Homepage containing:
    - Top 5 highest rated running projects in slider
    - Latest 5 projects
    - Latest 5 featured projects
    - Available categories
    - Search functionality
    """
    now = timezone.now()
    running_projects = Project.objects.filter(status='running', end_time__gte=now)

    # 1. Top 5 highest rated running projects
    # Annotate with average rating and sort descending
    top_rated_projects = running_projects.annotate(
        avg_score=Avg('ratings__score')
    ).order_by('-avg_score', '-created_at')[:5]

    # 2. Latest 5 projects
    latest_projects = Project.objects.filter(status='running').order_by('-created_at')[:5]

    # 3. Latest 5 featured projects selected by admin
    featured_projects = Project.objects.filter(
        is_featured=True, status='running'
    ).order_by('-created_at')[:5]

    # 4. Categories list with project counts
    categories = Category.objects.annotate(
        project_count=Count('projects', filter=Q(projects__status='running'))
    ).order_by('name')

    context = {
        'top_rated_projects': top_rated_projects,
        'latest_projects': latest_projects,
        'featured_projects': featured_projects,
        'categories': categories,
    }
    return render(request, 'home.html', context)


def project_list_view(request):
    """
    Explore all projects with searching, category & tag filtering, and pagination.
    """
    query = request.GET.get('q', '').strip()
    tag_slug = request.GET.get('tag', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest')

    projects = Project.objects.filter(status='running').select_related('category', 'creator').prefetch_related('images', 'tags')

    selected_category = None
    selected_tag = None

    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        projects = projects.filter(category=selected_category)

    if tag_slug:
        selected_tag = get_object_or_404(Tag, slug=tag_slug)
        projects = projects.filter(tags=selected_tag)

    if query:
        # Search by title or tag name (case-insensitive)
        projects = projects.filter(
            Q(title__icontains=query) |
            Q(details__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    if sort_by == 'target_high':
        projects = projects.order_by('-total_target')
    elif sort_by == 'target_low':
        projects = projects.order_by('total_target')
    elif sort_by == 'oldest':
        projects = projects.order_by('created_at')
    else:  # default latest
        projects = projects.order_by('-created_at')

    paginator = Paginator(projects, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'selected_category': selected_category,
        'selected_tag': selected_tag,
        'sort_by': sort_by,
        'all_categories': Category.objects.all(),
        'popular_tags': Tag.objects.annotate(p_count=Count('projects')).order_by('-p_count')[:15],
    }
    return render(request, 'projects/project_list.html', context)


def category_projects_view(request, slug):
    """View all projects under a specific category."""
    category = get_object_or_404(Category, slug=slug)
    projects = Project.objects.filter(category=category, status='running').order_by('-created_at')

    paginator = Paginator(projects, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'projects/category_projects.html', context)


def project_detail_view(request, pk):
    """
    Project details page displaying:
    - Title, details, creator, category, tags
    - Multiple images slider
    - Target, total donated, progress %, remaining
    - Start/end time, status
    - Average rating, user's rating
    - Comments with replies
    - Donation form
    - Report buttons
    - 4 Similar projects based on tags (with fallback to category)
    """
    project = get_object_or_404(
        Project.objects.select_related('category', 'creator').prefetch_related('images', 'tags'),
        pk=pk
    )

    # 4 Similar Projects based on tags (fallback to category), excluding current project
    project_tags = project.tags.all()
    similar_projects = Project.objects.filter(
        status='running'
    ).exclude(pk=project.pk)

    if project_tags.exists():
        # Match projects having overlapping tags, ordered by count of shared tags
        similar_tag_projects = similar_projects.filter(
            tags__in=project_tags
        ).annotate(
            shared_tags=Count('tags', filter=Q(tags__in=project_tags))
        ).order_by('-shared_tags', '-created_at').distinct()[:4]
        
        similar_list = list(similar_tag_projects)
    else:
        similar_list = []

    # If fewer than 4 similar projects found by tags, fallback to category
    if len(similar_list) < 4:
        needed = 4 - len(similar_list)
        already_ids = [p.pk for p in similar_list] + [project.pk]
        category_fallback = similar_projects.filter(
            category=project.category
        ).exclude(pk__in=already_ids).order_by('-created_at')[:needed]
        similar_list.extend(list(category_fallback))

    # Top-level comments with replies
    comments = project.comments.filter(parent__isnull=True).select_related('user').prefetch_related('replies__user').order_by('-created_at')

    # Current user's rating if authenticated
    user_rating = None
    if request.user.is_authenticated:
        user_rating = project.ratings.filter(user=request.user).first()

    donation_form = DonationForm()
    comment_form = CommentForm()
    rating_form = RatingForm(initial={'score': user_rating.score} if user_rating else None)
    report_form = ProjectReportForm()
    comment_report_form = CommentReportForm()

    context = {
        'project': project,
        'similar_projects': similar_list,
        'comments': comments,
        'user_rating': user_rating,
        'donation_form': donation_form,
        'comment_form': comment_form,
        'rating_form': rating_form,
        'report_form': report_form,
        'comment_report_form': comment_report_form,
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
def project_create_view(request):
    """Creates a new fundraising project campaign with tags and multiple images."""
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.creator = request.user
            project.save()

            # Handle Tags
            tags_str = form.cleaned_data.get('tags_input', '')
            if tags_str:
                tag_names = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
                for t_name in tag_names:
                    tag_obj, _ = Tag.objects.get_or_create(name=t_name, defaults={'slug': slugify(t_name)})
                    project.tags.add(tag_obj)

            # Handle Multiple Images
            uploaded_files = request.FILES.getlist('images')
            for index, file in enumerate(uploaded_files):
                ProjectImage.objects.create(
                    project=project,
                    image=file,
                    is_cover=(index == 0)
                )

            messages.success(request, f'Campaign "{project.title}" created successfully!')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        # Default start date now, default end date 30 days later
        initial_start = timezone.now()
        initial_end = initial_start + timezone.timedelta(days=30)
        form = ProjectForm(initial={
            'start_time': initial_start.strftime('%Y-%m-%dT%H:%M'),
            'end_time': initial_end.strftime('%Y-%m-%dT%H:%M'),
        })

    return render(request, 'projects/project_form.html', {'form': form, 'is_edit': False})


@login_required
def project_edit_view(request, pk):
    """Allows project creator to edit project details and add more images."""
    project = get_object_or_404(Project, pk=pk)

    if project.creator != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this project.')
        return redirect('projects:project_detail', pk=project.pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save()

            # Update Tags
            tags_str = form.cleaned_data.get('tags_input', '')
            project.tags.clear()
            if tags_str:
                tag_names = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
                for t_name in tag_names:
                    tag_obj, _ = Tag.objects.get_or_create(name=t_name, defaults={'slug': slugify(t_name)})
                    project.tags.add(tag_obj)

            # Handle Newly Uploaded Images
            uploaded_files = request.FILES.getlist('images')
            has_cover = project.images.filter(is_cover=True).exists()
            for index, file in enumerate(uploaded_files):
                ProjectImage.objects.create(
                    project=project,
                    image=file,
                    is_cover=(not has_cover and index == 0)
                )

            messages.success(request, 'Campaign updated successfully!')
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {'form': form, 'project': project, 'is_edit': True})


@login_required
def project_image_delete_view(request, project_id, image_id):
    """
    Deletes a single project image belonging to a specific campaign.
    Enforces authorization:
    - User must be authenticated
    - Project must exist
    - Image must exist and belong directly to the project
    - User must be project creator or staff/admin
    - Rejects unauthorized users with 403 Forbidden
    - Removes physical image file from storage
    - Automatically updates cover image if deleted image was cover
    """
    project = get_object_or_404(Project, pk=project_id)
    image = get_object_or_404(ProjectImage, pk=image_id, project=project)

    if project.creator != request.user and not request.user.is_staff:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'error': 'You do not have permission to delete this image.'}, status=403)
        return HttpResponseForbidden('You do not have permission to delete this image.')

    if request.method in ['POST', 'DELETE']:
        was_cover = image.is_cover

        # Delete physical file from storage
        if image.image:
            try:
                storage = image.image.storage
                name = image.image.name
                if storage and name and storage.exists(name):
                    storage.delete(name)
            except Exception:
                pass

        # Delete database record
        image.delete()

        # If deleted image was cover, assign cover to the next available image
        if was_cover:
            next_image = project.images.first()
            if next_image:
                next_image.is_cover = True
                next_image.save(update_fields=['is_cover'])

        remaining_count = project.images.count()
        new_cover_url = project.cover_image

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Image deleted successfully.',
                'image_id': image_id,
                'remaining_count': remaining_count,
                'new_cover_url': new_cover_url
            })

        messages.success(request, 'Image deleted successfully.')
        return redirect('projects:project_edit', pk=project.pk)

    return redirect('projects:project_edit', pk=project.pk)


@login_required
def project_cancel_view(request, pk):
    """
    Project Cancellation Business Rule:
    Project creator can cancel the project ONLY IF total donations are less than 25% of target.
    """
    project = get_object_or_404(Project, pk=pk)

    if project.creator != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to cancel this project.')
        return redirect('projects:project_detail', pk=project.pk)

    if project.status == 'cancelled':
        messages.warning(request, 'This project has already been cancelled.')
        return redirect('projects:project_detail', pk=project.pk)

    if not project.can_be_cancelled:
        messages.error(
            request,
            'Project cannot be cancelled! Total donations have reached or exceeded 25% of the target.'
        )
        return redirect('projects:project_detail', pk=project.pk)

    if request.method == 'POST':
        project.status = 'cancelled'
        project.save()
        messages.success(request, f'Project "{project.title}" has been successfully cancelled.')
        return redirect('projects:project_detail', pk=project.pk)

    context = {
        'project': project,
        'twenty_five_percent_target': project.total_target * Decimal('0.25'),
    }
    return render(request, 'projects/project_cancel.html', context)


@login_required
def donate_view(request, pk):
    """Processes a donation to a project."""
    project = get_object_or_404(Project, pk=pk)

    if request.method != 'POST':
        return redirect('projects:project_detail', pk=pk)

    if project.status != 'running' or project.is_expired:
        messages.error(request, 'Donations cannot be accepted for inactive, expired, or cancelled campaigns.')
        return redirect('projects:project_detail', pk=pk)

    form = DonationForm(request.POST)
    if form.is_valid():
        amount = form.cleaned_data['amount']
        Donation.objects.create(
            user=request.user,
            project=project,
            amount=amount
        )
        messages.success(request, f'Thank you! Your donation of {amount:,.2f} EGP to "{project.title}" was successful.')
    else:
        for error in form.errors.values():
            messages.error(request, error)

    return redirect('projects:project_detail', pk=pk)


@login_required
def add_comment_view(request, pk):
    """Adds a top-level comment or a reply to an existing comment."""
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data['content']
            parent_id = form.cleaned_data.get('parent_id')
            parent_comment = None

            if parent_id:
                try:
                    parent_comment = Comment.objects.get(pk=parent_id, project=project)
                    # Limit to 1 level of reply
                    if parent_comment.parent is not None:
                        parent_comment = parent_comment.parent
                except Comment.DoesNotExist:
                    parent_comment = None

            Comment.objects.create(
                user=request.user,
                project=project,
                content=content,
                parent=parent_comment
            )
            messages.success(request, 'Your comment was posted!')
        else:
            messages.error(request, 'Failed to post comment. Please provide valid text.')

    return redirect('projects:project_detail', pk=pk)


@login_required
def rate_project_view(request, pk):
    """Rates a project between 1 and 5 stars."""
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            score = int(form.cleaned_data['score'])
            Rating.objects.update_or_create(
                user=request.user,
                project=project,
                defaults={'score': score}
            )
            messages.success(request, f'You rated this project {score} stars. Thank you for your feedback!')
        else:
            messages.error(request, 'Please select a valid rating from 1 to 5 stars.')

    return redirect('projects:project_detail', pk=pk)


@login_required
def remove_rating_view(request, pk):
    """
    Allows the authenticated user to remove their own rating from a project.
    """
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        rating = Rating.objects.filter(user=request.user, project=project).first()
        if rating:
            rating.delete()
            messages.success(request, 'Your rating has been removed.')
        else:
            messages.info(request, 'You have not rated this project.')

    return redirect('projects:project_detail', pk=pk)



@login_required
def report_project_view(request, pk):
    """Reports an inappropriate project."""
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = ProjectReportForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            # Check for existing pending report
            existing = ProjectReport.objects.filter(
                reporter=request.user,
                project=project,
                status='pending'
            ).exists()

            if existing:
                messages.info(request, 'You already have a pending report for this project. Our team is reviewing it.')
            else:
                ProjectReport.objects.create(
                    reporter=request.user,
                    project=project,
                    reason=reason
                )
                messages.success(request, 'Thank you. Your report has been submitted to the admin team for review.')
        else:
            messages.error(request, 'Please enter a valid reason for the report.')

    return redirect('projects:project_detail', pk=pk)


@login_required
def report_comment_view(request, pk, comment_id):
    """Reports an inappropriate comment."""
    project = get_object_or_404(Project, pk=pk)
    comment = get_object_or_404(Comment, pk=comment_id, project=project)

    if request.method == 'POST':
        form = CommentReportForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            existing = CommentReport.objects.filter(
                reporter=request.user,
                comment=comment,
                status='pending'
            ).exists()

            if existing:
                messages.info(request, 'You already have a pending report for this comment.')
            else:
                CommentReport.objects.create(
                    reporter=request.user,
                    comment=comment,
                    reason=reason
                )
                messages.success(request, 'Comment reported to moderators.')
        else:
            messages.error(request, 'Please specify the reason for reporting this comment.')

    return redirect('projects:project_detail', pk=pk)


@login_required
def delete_comment_view(request, pk, comment_id):
    """
    Deletes a comment or reply.
    Only the comment owner or an authorized admin/staff user can delete it.
    """
    project = get_object_or_404(Project, pk=pk)
    comment = get_object_or_404(Comment, pk=comment_id, project=project)

    if request.method == 'POST':
        # Enforce strict ownership / admin permission check
        if comment.user != request.user and not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("You do not have permission to delete this comment.")

        comment.delete()
        messages.success(request, 'Comment deleted successfully.')

    return redirect('projects:project_detail', pk=pk)



@login_required
def my_projects_view(request):
    """Shortcut view to show user's created projects."""
    projects = request.user.projects.all().order_by('-created_at')
    return render(request, 'projects/my_projects.html', {'projects': projects})


@login_required
def my_donations_view(request):
    """Shortcut view to show user's donations."""
    donations = request.user.donations.select_related('project').order_by('-created_at')
    return render(request, 'projects/my_donations.html', {'donations': donations})
