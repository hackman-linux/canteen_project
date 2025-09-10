from django.apps import AppConfig

class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
    label = "authentication"   # app label used in AUTH_USER_MODEL
