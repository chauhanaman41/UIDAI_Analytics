from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.core.cache import cache
from .tasks import calculate_trends_task, generate_anomaly_report_task, train_forecast_model_task, generate_insights_task
from celery.result import AsyncResult
from .services import enrollment, biometric, anomaly, forecasting
# try:
#     from .services import rag_explanation
# except Exception:
rag_explanation = None

# ... (Previous imports and views)

class EnrollmentTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = request.query_params.get('state')
        district = request.query_params.get('district')
        
        # Cache key generation
        cache_key = f"trends_{state}_{district}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)

        try:
            # Simple synchronous call for MVP, ideally cached or async for large queries
            # For now, we reuse the service logic which is fast enough for aggregate queries
            data = enrollment.calculate_growth_rates(state, district)
            # Cache for 15 minutes
            cache.set(cache_key, data, timeout=900)
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class BiometricSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = request.query_params.get('state')
        district = request.query_params.get('district')
        try:
            data = biometric.calculate_success_rates(state, district)
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class AnomalyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Retrieve latest anomaly report
        try:
            # converting df to dict for JSON response
            report = anomaly.comprehensive_anomaly_report()
            return Response(report)
        except Exception as e:
             return Response({"error": str(e)}, status=500)

class ForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, state):
        try:
            # Synchronous generation for MVP demo
            result = forecasting.generate_forecast_sync(state)
            return Response(result)
        except Exception as e:
             return Response({"error": str(e)}, status=500)

class AsyncAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_type):
        task_mapping = {
            'trends': calculate_trends_task,
            'anomalies': generate_anomaly_report_task,
            'forecast': train_forecast_model_task
        }
        
        if task_type not in task_mapping:
            return Response({"error": "Invalid task type"}, status=400)
            
        task = task_mapping[task_type].delay(**request.data)
        return Response({"task_id": task.id, "status": "Task started"})

class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        result = AsyncResult(task_id)
        return Response({
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None
        })

class InsightsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retrieve latest cached insights."""
        cached_result = cache.get("latest_insights")
        if cached_result:
            return Response(cached_result)
        return Response({"message": "No insights generated yet. Trigger generation via POST."}, status=404)

    def post(self, request):
        """Trigger async insight generation."""
        metrics_data = request.data.get("metrics", {})
        
        # If no metrics provided, mock pulling them from other services
        if not metrics_data:
             # In a real scenario, we would aggregate data from other service calls here
             # For now, we expect the frontend to pass the summary metrics it has
             pass

        task = generate_insights_task.delay(metrics_data)
        return Response({"task_id": task.id, "status": "Insight generation started"}, status=202)

class AnomalyExplanationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, anomaly_id):
        """
        Retrieves an explanation for a specific anomaly using RAG.
        """
        try:
            # 1. Fetch anomaly details (Mocking retrieval based on ID for MVP)
            # In production, query the Anomaly model by ID
            anomaly_record = {
                "anomaly_type": "Sharp Drop",
                "district": "Lucknow",
                "state": "Uttar Pradesh",
                "anomaly_value": "450 enrollments (expected 1200)",
                "date": "2023-10-15",
                "severity": 8,
                "description": "Unusual drop in daily enrollments despite working day."
            }
            
            # Simple mock logic to vary response based on ID
            if anomaly_id == "2":
                 anomaly_record.update({
                    "anomaly_type": "Biometric Failure Spike", 
                    "district": "Bangalore",
                    "state": "Karnataka",
                    "description": "High failure rate in fingerprint auth."
                 })

            # 2. Get explanation from RAG system
            if rag_explanation:
                result = rag_explanation.rag_system.explain_anomaly(anomaly_record)
            else:
                result = {"explanation": "RAG system not available (dependencies missing).", "similar_cases": []}
            
            return Response({
                "anomaly": anomaly_record,
                "rag_explanation": result
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request, anomaly_id):
         """Index a new anomaly (Helper for demo population)."""
         try:
             if not rag_explanation:
                 return Response({"error": "RAG system not available"}, status=503)
             record = request.data
             rag_explanation.rag_system.index_anomaly(record)
             return Response({"status": "Indexed successfully"})
             return Response({"status": "Indexed successfully"})
         except Exception as e:
             return Response({"error": str(e)}, status=500)

from .models import PolicyRecommendation
from .serializers import PolicyRecommendationSerializer

class RecommendationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            recommendations = PolicyRecommendation.objects.all()
            serializer = PolicyRecommendationSerializer(recommendations, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class DataUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES['file']
        # In a real scenario, save file to storage and pass path to Celery
        # For prototype, we might process strictly or mock the ETL trigger
        
        # Trigger ETL Task (Mocked for now or hook into real task if exists)
        # task = etl_process_task.delay(file_path)
        # For this integration test workflow:
        task_id = "mock-etl-task-id-123" 
        # In reality: task_id = run_etl.delay(file_path).id
        
        return Response({"message": "Upload accepted", "task_id": task_id}, status=status.HTTP_202_ACCEPTED)

