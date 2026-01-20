from rest_framework import serializers
from .models import AnomalyAlert

class AnomalyAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyAlert
        fields = '__all__'

class ForecastSerializer(serializers.Serializer):
    state = serializers.CharField()
    forecast = serializers.ListField()
    model_used = serializers.CharField()
    mape = serializers.FloatField()

class RiskSerializer(serializers.Serializer):
    district = serializers.CharField()
    risk_score = serializers.FloatField()
    risk_category = serializers.CharField()
    top_factors = serializers.ListField()

class GrowthRateSerializer(serializers.Serializer):
    date = serializers.CharField()
    age_group = serializers.CharField()
    growth_rate_pct = serializers.IntegerField()
    absolute_change = serializers.IntegerField()

class EnrollmentTrendsSerializer(serializers.Serializer):
    Monthly_MoM = GrowthRateSerializer(many=True)
    Quarterly_QoQ = GrowthRateSerializer(many=True)
    Yearly_YoY = GrowthRateSerializer(many=True)

class BiometricSuccessSerializer(serializers.Serializer):
    state = serializers.CharField()
    district = serializers.CharField()
    date = serializers.CharField()
    success_rate_5_17 = serializers.FloatField()
    success_rate_17_plus = serializers.FloatField()

    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(required=False)

from .models import PolicyRecommendation

class PolicyRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyRecommendation
        fields = '__all__'
