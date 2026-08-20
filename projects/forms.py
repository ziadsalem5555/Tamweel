from decimal import Decimal
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Project, Category, Tag, Donation, Comment, Rating, ProjectReport, CommentReport


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ProjectForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        empty_label="-- Select Category --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tags_input = forms.CharField(
        label=_('Tags (comma-separated)'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. tech, health, cairo, education'
        }),
        help_text=_('Enter tags separated by commas')
    )
    images = MultipleFileField(
        label=_('Project Images'),
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'multiple': True
        }),
        help_text=_('Upload one or more pictures for your project slider')
    )

    class Meta:
        model = Project
        fields = ['title', 'details', 'category', 'total_target', 'start_time', 'end_time']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Campaign Title'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Describe your campaign story, goals, and how funds will be used...'}),
            'total_target': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 250000', 'min': '1', 'step': '0.01'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Populate tags_input from existing tags
            self.fields['tags_input'].initial = ', '.join(t.name for t in self.instance.tags.all())

    def clean_total_target(self):
        target = self.cleaned_data.get('total_target')
        if target is None or target <= 0:
            raise ValidationError(_('Target fundraising amount must be a positive number greater than 0.'))
        return target

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if end_time <= start_time:
                self.add_error('end_time', _('End date and time must be after the start date and time.'))

        return cleaned_data


class DonationForm(forms.ModelForm):
    amount = forms.DecimalField(
        min_value=Decimal('1.00'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Amount in EGP (e.g. 500)',
            'min': '1',
            'step': '0.01'
        })
    )

    class Meta:
        model = Donation
        fields = ['amount']


class CommentForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Write your comment or question here...'
        })
    )
    parent_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Comment
        fields = ['content']


class RatingForm(forms.ModelForm):
    score = forms.ChoiceField(
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')],
        widget=forms.RadioSelect()
    )

    class Meta:
        model = Rating
        fields = ['score']


class ProjectReportForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Please explain why you are reporting this project...'
        })
    )

    class Meta:
        model = ProjectReport
        fields = ['reason']


class CommentReportForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please explain why you are reporting this comment...'
        })
    )

    class Meta:
        model = CommentReport
        fields = ['reason']
