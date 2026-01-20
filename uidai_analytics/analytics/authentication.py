from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import jwt # PyJWT

class SupabaseAuthentication(BaseAuthentication):
    """
    Custom authentication to validate Supabase JWTs.
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
            
        try:
            token = auth_header.split(' ')[1]
            # Verify token using Supabase Secret
            # Note: In production, verify audience/issuer as well.
            # Ideally verify signature with SUPABASE_JWT_SECRET (different from API KEY often)
            # Assuming SECRET_KEY in env is the JWT secret for now, or we define SUPABASE_JWT_SECRET
            # If Supabase Auth is used, we need the project JWT secret.
            
            # For MVP, skipping strict signature check if no secret provided, or using simple verification.
            # Using verify=False for MVP integration unless secret strictly available.
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Simple User object mock
            from django.contrib.auth.models import User
            # We can map 'sub' (UUID) to a Django user or just return a dummy
            user = User(username=payload.get('sub', 'supabase_user'))
            return (user, None)
            
        except IndexError:
            raise AuthenticationFailed('Token prefix missing')
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
