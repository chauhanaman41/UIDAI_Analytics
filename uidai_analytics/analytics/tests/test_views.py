import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APITestCase
from django.contrib.auth.models import User

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user(db):
    from django.contrib.auth.models import User
    return User.objects.create_user(username='testuser', password='password')

@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client

@pytest.mark.django_db
class TestEnrollmentTrendsView:
    @patch('analytics.services.enrollment.calculate_growth_rates')
    def test_trends_endpoint_success(self, mock_calc, auth_client):
        mock_calc.return_value = {
            "Monthly_MoM": [{"growth_rate_pct": 5}], 
            "Quarterly_QoQ": [], 
            "Yearly_YoY": []
        }
        url = reverse('enrollment-trends')
        response = auth_client.get(url, {'state': 'Maharashtra'})
        
        assert response.status_code == 200
        assert response.json()['Monthly_MoM'][0]['growth_rate_pct'] == 5

    def test_trends_endpoint_unauthorized(self, client):
        url = reverse('enrollment-trends')
        response = client.get(url)
        assert response.status_code == 403

    @patch('analytics.services.enrollment.calculate_growth_rates')
    def test_trends_endpoint_error(self, mock_calc, auth_client):
        mock_calc.side_effect = Exception("DB Error")
        url = reverse('enrollment-trends')
        response = auth_client.get(url)
        
        assert response.status_code == 500
        assert "error" in response.json()

@pytest.mark.django_db
@patch('analytics.views.anomaly.comprehensive_anomaly_report')
def test_anomaly_list_success_view(mock_report, auth_client):
    # Set return value to avoid running real code or breaking serialization
    mock_report.return_value = [{"date": "2023-01-01", "anomaly_value": 100}]
    
    # Still create generic SQL-agnostic dummy data if needed by Django parts
    # But now patch should stop SQL execution in service.
    from analytics.models import AnomalyAlert
    # ...
    url = reverse('anomalies')
    response = auth_client.get(url)
    
    assert response.status_code == 200
    # Check specific structure depending on view implementation
    # Assuming list response or dict with key 'anomalies'
    data = response.json()
    if isinstance(data, list):
            assert len(data) >= 1
    elif 'results' in data: # Pagination
            assert len(data['results']) >= 1
    else:
            # Fallback check
            assert len(data) >= 1

class TestForecastView:
    @patch('analytics.services.forecasting.generate_forecast_sync')
    def test_forecast_success(self, mock_forecast, auth_client):
        mock_forecast.return_value = {"forecast": []}
        url = reverse('forecasts', args=['Delhi'])
        response = auth_client.get(url)
        
        assert response.status_code == 200

class TestPolicyRecommendationsView:
    @pytest.mark.django_db
    def test_recommendations_list(self, auth_client):
        from analytics.models import PolicyRecommendation
        PolicyRecommendation.objects.create(
            district="Test D", state="Test S", 
            recommendation="Fix it", rationale="Why", 
            impact_estimate="High", priority="High"
        )
        url = reverse('recommendations')
        response = auth_client.get(url)
        
        assert response.status_code == 200
        assert len(response.json()) >= 1
        assert response.json()[0]['district'] == "Test D"
