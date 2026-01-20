from django.db import models

class Enrollment(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateField()
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6, null=True, blank=True)
    age_0_5 = models.IntegerField()
    age_5_17 = models.IntegerField()
    age_18_greater = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False  # Managed by Supabase
        db_table = 'enrollments'
        indexes = [
            models.Index(fields=['state', 'district']),
            models.Index(fields=['date']),
            models.Index(fields=['state', 'date']),
        ]

class BiometricAttempt(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateField()
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6, null=True, blank=True)
    bio_age_5_17 = models.IntegerField()
    bio_age_17_plus = models.IntegerField(db_column='bio_age_17_') # Encapsulate DB column name
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'biometric_attempts'
        indexes = [
            models.Index(fields=['state', 'district']),
            models.Index(fields=['date']),
        ]

class AnomalyAlert(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateField()
    state = models.CharField(max_length=100, null=True)
    district = models.CharField(max_length=100, null=True)
    metric_name = models.CharField(max_length=100)
    anomaly_value = models.FloatField()
    severity_score = models.FloatField(null=True)
    anomaly_type = models.CharField(max_length=50, null=True)
    # detecting_methods is TEXT[] in Postgres, Django ArrayField requires psycopg2
    # For MVP, we can treat as string or use specific ArrayField if postgres specific features enabled
    # Let's import ArrayField
    from django.contrib.postgres.fields import ArrayField
    detection_methods = ArrayField(models.CharField(max_length=50), null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'anomaly_alerts'

class PolicyRecommendation(models.Model):
    district = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    issue_type = models.CharField(max_length=255)
    recommendation = models.TextField()
    rationale = models.TextField()
    impact_estimate = models.CharField(max_length=255)
    priority = models.CharField(max_length=50) # High, Medium, Low
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
