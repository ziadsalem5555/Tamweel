from django.contrib import admin
from .models import (
    Category, Tag, Project, ProjectImage, Donation,
    Rating, Comment, ProjectReport, CommentReport
)


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'category', 'total_target', 'status', 'is_featured', 'created_at')
    list_filter = ('status', 'is_featured', 'category', 'created_at')
    search_fields = ('title', 'details', 'creator__email', 'creator__first_name', 'creator__last_name')
    filter_horizontal = ('tags',)
    inlines = [ProjectImageInline]
    actions = ['make_featured', 'unmake_featured', 'mark_completed']

    @admin.action(description='Mark selected projects as Featured')
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description='Remove selected projects from Featured')
    def unmake_featured(self, request, queryset):
        queryset.update(is_featured=False)

    @admin.action(description='Mark selected projects as Completed')
    def mark_completed(self, request, queryset):
        queryset.update(status='completed')


@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ('project', 'is_cover', 'created_at')
    list_filter = ('is_cover', 'created_at')
    search_fields = ('project__title',)


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'amount', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'project__title')
    ordering = ('-created_at',)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'score', 'created_at', 'updated_at')
    list_filter = ('score', 'created_at')
    search_fields = ('user__email', 'project__title')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'parent', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'project__title', 'content')


@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = ('project', 'reporter', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('project__title', 'reporter__email', 'reason')
    actions = ['mark_reviewed', 'mark_resolved', 'mark_rejected']

    @admin.action(description='Mark selected reports as Reviewed')
    def mark_reviewed(self, request, queryset):
        queryset.update(status='reviewed')

    @admin.action(description='Mark selected reports as Resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved')

    @admin.action(description='Mark selected reports as Rejected')
    def mark_rejected(self, request, queryset):
        queryset.update(status='rejected')


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('comment', 'reporter', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reporter__email', 'reason')
    actions = ['mark_reviewed', 'mark_resolved', 'mark_rejected']

    @admin.action(description='Mark selected reports as Reviewed')
    def mark_reviewed(self, request, queryset):
        queryset.update(status='reviewed')

    @admin.action(description='Mark selected reports as Resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved')

    @admin.action(description='Mark selected reports as Rejected')
    def mark_rejected(self, request, queryset):
        queryset.update(status='rejected')
