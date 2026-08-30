from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list_view, name='project_list'),
    path('category/<slug:slug>/', views.category_projects_view, name='category_projects'),
    path('create/', views.project_create_view, name='project_create'),
    path('<int:pk>/', views.project_detail_view, name='project_detail'),
    path('<int:pk>/edit/', views.project_edit_view, name='project_edit'),
    path('<int:project_id>/images/<int:image_id>/delete/', views.project_image_delete_view, name='project_image_delete'),
    path('<int:pk>/cancel/', views.project_cancel_view, name='project_cancel'),
    path('<int:pk>/donate/', views.donate_view, name='donate'),
    path('<int:pk>/comment/', views.add_comment_view, name='add_comment'),
    path('<int:pk>/rate/', views.rate_project_view, name='rate_project'),
    path('<int:pk>/rate/remove/', views.remove_rating_view, name='remove_rating'),
    path('<int:pk>/report/', views.report_project_view, name='report_project'),
    path('<int:pk>/comment/<int:comment_id>/report/', views.report_comment_view, name='report_comment'),
    path('<int:pk>/comment/<int:comment_id>/delete/', views.delete_comment_view, name='delete_comment'),
    path('my-projects/', views.my_projects_view, name='my_projects'),
    path('my-donations/', views.my_donations_view, name='my_donations'),
]
