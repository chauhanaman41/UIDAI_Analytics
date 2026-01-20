from django.urls import path
from .views import (
    EnrollmentTrendsView, BiometricSuccessView, AnomalyListView, 
    ForecastView, AsyncAnalyticsView, TaskStatusView,
    InsightsView, AnomalyExplanationView, RecommendationListView
)
from . import views

urlpatterns = [
    path('enrollments/trends/', views.EnrollmentTrendsView.as_view(), name='enrollment-trends'),
    path('biometric/success-rates/', views.BiometricSuccessView.as_view(), name='biometric-success'),
    path('anomalies/', views.AnomalyListView.as_view(), name='anomalies'),
    path('forecasts/<str:state>/', views.ForecastView.as_view(), name='forecasts'),
    path('analytics/run/<str:task_type>/', views.AsyncAnalyticsView.as_view(), name='async-run'),
    path('analytics/status/<str:task_id>/', views.TaskStatusView.as_view(), name='task-status'),
    path('insights/generate/', views.InsightsView.as_view(), name='generate-insights'),
    path('data/upload/', views.DataUploadView.as_view(), name='data-upload'),
    path('anomalies/<str:anomaly_id>/explain/', views.AnomalyExplanationView.as_view(), name='explain-anomaly'),
    path('recommendations/', views.RecommendationListView.as_view(), name='recommendations'),
]
