from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('slips/create/', views.create_slip_view, name='create_slip'),
    path('slips/<int:pk>/edit/', views.edit_slip_view, name='edit_slip'),
    path('slips/<int:pk>/delete/', views.delete_slip_view, name='delete_slip'),
    path('slips/<int:pk>/download/', views.download_slip_view, name='download_slip'),
    path('recipients/', views.recipient_list_view, name='recipient_list'),
    path('recipients/add/', views.add_recipient_view, name='add_recipient'),
    path('recipients/<int:pk>/edit/', views.edit_recipient_view, name='edit_recipient'),
    path('recipients/<int:pk>/delete/', views.delete_recipient_view, name='delete_recipient'),
    path('custom-print/', views.custom_print_view, name='custom_print'),
]   