from django.urls import path
from . import views

urlpatterns = [
    path('collections/', views.collection_list_view, name='collection_list'),
    path('collections/<int:pk>/', views.collection_detail_view, name='collection_detail'),
]