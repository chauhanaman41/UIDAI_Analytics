import pytest
from unittest.mock import patch, MagicMock
from analytics.tasks import calculate_trends_task, generate_anomaly_report_task, generate_weekly_policy_report

@pytest.mark.django_db
class TestCeleryTasks:
    
    @patch('analytics.tasks.enrollment.calculate_growth_rates')
    def test_calculate_trends_task(self, mock_calc):
        mock_calc.return_value = {"status": "ok"}
        
        # Build arguments. Note: self is injected by celery, we pass args via apply
        # Call via apply() to ensure task_id is present for backend
        result = calculate_trends_task.apply(kwargs={"state": "Goa"}, task_id="test-task-1")
        
        assert result.result == {"status": "ok"}
        mock_calc.assert_called_once()

    @patch('analytics.tasks.anomaly.detect_anomalies_daily_sync')
    def test_anomaly_task(self, mock_detect):
        result = generate_anomaly_report_task({"state": "All"})
        
        assert result['status'] == 'success'
        mock_detect.assert_called_once()

    @patch('analytics.tasks.policy.generate_policy_recommendations')
    @patch('analytics.tasks.PolicyRecommendation.objects.create')
    def test_policy_report_task(self, mock_create, mock_gen):
        mock_gen.return_value = [{
            "district": "D1", "recommendation": "R1", 
            "rationale": "Ra1", "impact_estimate": "I1", "priority": "High"
        }]
        
        result = generate_weekly_policy_report()
        
        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_create.assert_called_once()
