from .models import AuditLog

def create_audit_log(user, activity, description="", ip=None):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        activity=activity,
        description=description,
        ip_address=ip,
    )
