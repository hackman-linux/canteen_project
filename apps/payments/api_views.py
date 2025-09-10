from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
import json

from .models import Payment


# -----------------------
# Custom Decorator Inline
# -----------------------
def logout_after_response(func):
    """
    Decorator: forces logout after executing the view
    (only for payment endpoints).
    """
    def wrapper(request, *args, **kwargs):
        response = func(request, *args, **kwargs)
        logout(request)  # force logout after the response
        return response
    return wrapper


# -----------------------
# Payment API Views
# -----------------------
@csrf_exempt
@login_required
@logout_after_response
@require_http_methods(["GET"])
def payment_list(request):
    """
    Return a list of payments for the logged-in user.
    """
    payments = Payment.objects.filter(user=request.user).values(
        "id", "user_id", "amount", "status", "transaction_id", "created_at"
    )
    return JsonResponse(list(payments), safe=False, status=200)


@csrf_exempt
@login_required
@logout_after_response
@require_http_methods(["GET"])
def payment_detail(request, payment_id):
    """
    Return details of a single payment (only owner or staff).
    """
    try:
        payment = Payment.objects.get(id=payment_id)

        if request.user != payment.user and not request.user.is_staff:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        return JsonResponse({
            "id": payment.id,
            "user_id": payment.user_id,
            "amount": payment.amount,
            "status": payment.status,
            "transaction_id": payment.transaction_id,
            "created_at": payment.created_at,
        }, status=200)

    except ObjectDoesNotExist:
        return JsonResponse({"error": "Payment not found"}, status=404)


@csrf_exempt
@login_required
@logout_after_response
@require_http_methods(["POST"])
def initiate_payment(request):
    """
    Initiate a new payment for the logged-in user.
    Expected JSON: { "amount": 1000 }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
        amount = data.get("amount")

        if not amount:
            return JsonResponse({"error": "amount is required"}, status=400)

        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            status="pending",
            transaction_id=f"TXN{timezone.now().strftime('%Y%m%d%H%M%S')}"
        )

        return JsonResponse(
            {
                "message": "Payment initiated",
                "payment_id": payment.id,
                "transaction_id": payment.transaction_id,
            },
            status=201,
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@login_required
@logout_after_response
@require_http_methods(["GET"])
def payment_status(request, transaction_id):
    """
    Check payment status by transaction_id.
    """
    try:
        payment = Payment.objects.get(transaction_id=transaction_id)

        if request.user != payment.user and not request.user.is_staff:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        return JsonResponse({
            "id": payment.id,
            "transaction_id": payment.transaction_id,
            "status": payment.status,
            "amount": payment.amount,
            "user_id": payment.user_id,
        }, status=200)

    except ObjectDoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)


@csrf_exempt
@login_required
@logout_after_response
@require_http_methods(["POST"])
def refund_payment(request, transaction_id):
    """
    Process refund for a given transaction_id (staff only).
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "Only admins can process refunds"}, status=403)

    try:
        payment = Payment.objects.get(transaction_id=transaction_id)

        if payment.status != "completed":
            return JsonResponse({"error": "Only completed payments can be refunded"}, status=400)

        payment.status = "refunded"
        payment.save()

        return JsonResponse({"message": "Refund processed", "transaction_id": transaction_id}, status=200)

    except ObjectDoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)
