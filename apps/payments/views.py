from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
import uuid
import requests
import logging

from .models import Payment, WalletTransaction, PaymentProvider, PaymentWebhook
from apps.orders.models import Order
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)

@csrf_exempt
def initiate_payment(request):
    return JsonResponse({"message": "Payment initiation placeholder"})

@login_required
def proceed_to_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, employee=request.user)
    if order.status != "VALIDATED":
        messages.error(request, "Order not validated yet.")
        return redirect("orders:history")
    return render(request, "payment_checkout.html", {"order": order})


@login_required
def payment_status(request, transaction_id):
    return JsonResponse({"transaction_id": transaction_id, "status": "pending"})

@login_required
def refund_payment(request, transaction_id):
    return JsonResponse({"transaction_id": transaction_id, "status": "refunded"})


@login_required
def process_payment(request):
    """Process payment for an order"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order_id = data.get('order_id')
            payment_method = data.get('payment_method')
            phone_number = data.get('phone_number', '')
            
            # Get order
            order = get_object_or_404(Order, id=order_id, customer=request.user)
            
            if order.status != 'pending':
                return JsonResponse({'error': 'Order cannot be paid'}, status=400)
            
            # Check if payment already exists
            if order.payments.filter(status__in=['pending', 'completed']).exists():
                return JsonResponse({'error': 'Payment already processed'}, status=400)
            
            with transaction.atomic():
                # Create payment record
                payment = Payment.objects.create(
                    user=request.user,
                    order=order,
                    payment_method=payment_method,
                    amount=order.total_amount,
                    phone_number=phone_number,
                    description=f'Payment for order #{order.order_number}'
                )
                
                # Process payment based on method
                if payment_method == 'wallet':
                    result = process_wallet_payment(payment)
                elif payment_method == 'mtn_momo':
                    result = process_mtn_payment(payment)
                elif payment_method == 'orange_money':
                    result = process_orange_payment(payment)
                else:
                    return JsonResponse({'error': 'Invalid payment method'}, status=400)
                
                if result['success']:
                    # Update order status
                    order.update_status('confirmed', request.user)
                    
                    return JsonResponse({
                        'success': True,
                        'message': result['message'],
                        'payment_id': str(payment.id),
                        'transaction_id': result.get('transaction_id', ''),
                        'redirect_url': result.get('redirect_url', '')
                    })
                else:
                    return JsonResponse({
                        'error': result['message']
                    }, status=400)
                    
        except Exception as e:
            logger.error(f'Payment processing error: {str(e)}')
            return JsonResponse({'error': 'Payment processing failed'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def process_wallet_payment(payment):
    """Process wallet payment"""
    try:
        user = payment.user
        amount = payment.amount
        
        # Check wallet balance
        if not user.has_sufficient_balance(amount):
            payment.mark_as_failed('Insufficient wallet balance')
            return {
                'success': False,
                'message': 'Insufficient wallet balance'
            }
        
        # Deduct from wallet
        old_balance = user.wallet_balance
        if user.deduct_from_wallet(amount):
            # Mark payment as completed
            payment.mark_as_completed()
            
            # Create wallet transaction
            WalletTransaction.objects.create(
                user=user,
                transaction_type='debit',
                source='order_payment',
                amount=amount,
                balance_before=old_balance,
                balance_after=user.wallet_balance,
                payment=payment,
                order=payment.order,
                description=f'Payment for order #{payment.order.order_number}',
                reference=payment.payment_reference
            )
            
            return {
                'success': True,
                'message': 'Payment completed successfully',
                'transaction_id': payment.payment_reference
            }
        else:
            payment.mark_as_failed('Failed to deduct from wallet')
            return {
                'success': False,
                'message': 'Payment failed'
            }
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return {
            'success': False,
            'message': 'Payment processing failed'
        }


def process_mtn_payment(payment):
    """Process MTN Mobile Money payment"""
    try:
        # Mark payment as processing
        payment.mark_as_processing()
        
        # MTN Mobile Money API integration
        mtn_config = settings.MTN_MOMO_CONFIG
        
        headers = {
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': mtn_config['SUBSCRIPTION_KEY'],
            'Authorization': f'Bearer {get_mtn_access_token()}',
            'X-Reference-Id': str(uuid.uuid4()),
            'X-Target-Environment': 'sandbox'  # Change to 'live' for production
        }
        
        payload = {
            'amount': str(payment.amount),
            'currency': 'XAF',
            'externalId': payment.payment_reference,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': payment.phone_number.replace('+', '')
            },
            'payerMessage': f'Payment for order #{payment.order.order_number}',
            'payeeNote': 'Enterprise Canteen Payment'
        }
        
        response = requests.post(
            f"{mtn_config['BASE_URL']}/collection/v1_0/requesttopay",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 202:
            # Payment request submitted successfully
            transaction_id = headers['X-Reference-Id']
            payment.transaction_id = transaction_id
            payment.save()
            
            return {
                'success': True,
                'message': 'Payment request sent. Please approve on your phone.',
                'transaction_id': transaction_id,
                'requires_approval': True
            }
        else:
            error_message = f'MTN API Error: {response.status_code}'
            payment.mark_as_failed(error_message)
            return {
                'success': False,
                'message': 'Failed to initiate MTN payment'
            }
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return {
            'success': False,
            'message': 'MTN payment processing failed'
        }


def process_orange_payment(payment):
    """Process Orange Money payment"""
    try:
        # Mark payment as processing
        payment.mark_as_processing()
        
        # Orange Money API integration
        orange_config = settings.ORANGE_MONEY_CONFIG
        
        # Get access token
        auth_response = requests.post(
            f"{orange_config['BASE_URL']}/oauth/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': orange_config['CLIENT_ID'],
                'client_secret': orange_config['CLIENT_SECRET']
            }
        )
        
        if auth_response.status_code != 200:
            payment.mark_as_failed('Orange authentication failed')
            return {
                'success': False,
                'message': 'Orange Money authentication failed'
            }
        
        access_token = auth_response.json()['access_token']
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        payload = {
            'merchant_key': orange_config['CLIENT_ID'],
            'currency': 'XAF',
            'order_id': payment.payment_reference,
            'amount': int(payment.amount),
            'return_url': orange_config['CALLBACK_URL'],
            'cancel_url': orange_config['CALLBACK_URL'],
            'notif_url': orange_config['CALLBACK_URL'],
            'lang': 'en',
            'reference': f'Order #{payment.order.order_number}'
        }
        
        response = requests.post(
            f"{orange_config['BASE_URL']}/webpayment",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 201:
            response_data = response.json()
            payment_url = response_data.get('payment_url')
            transaction_id = response_data.get('pay_token')
            
            payment.transaction_id = transaction_id
            payment.save()
            
            return {
                'success': True,
                'message': 'Redirecting to Orange Money...',
                'transaction_id': transaction_id,
                'redirect_url': payment_url
            }
        else:
            payment.mark_as_failed('Orange API error')
            return {
                'success': False,
                'message': 'Failed to initiate Orange Money payment'
            }
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return {
            'success': False,
            'message': 'Orange Money processing failed'
        }


def get_mtn_access_token():
    """Get MTN Mobile Money access token"""
    try:
        mtn_config = settings.MTN_MOMO_CONFIG
        
        headers = {
            'Ocp-Apim-Subscription-Key': mtn_config['SUBSCRIPTION_KEY'],
            'Authorization': f'Basic {mtn_config["API_KEY"]}'
        }
        
        response = requests.post(
            f"{mtn_config['BASE_URL']}/collection/token/",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            raise Exception('Failed to get MTN access token')
            
    except Exception as e:
        logger.error(f'MTN token error: {str(e)}')
        raise


@login_required
def process_topup(request):
    """Process wallet top-up"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = Decimal(data.get('amount', '0'))
            payment_method = data.get('payment_method')
            phone_number = data.get('phone_number', '')
            
            # Validate amount
            if amount <= 0:
                return JsonResponse({'error': 'Invalid amount'}, status=400)
            
            if amount < 100:  # Minimum top-up amount
                return JsonResponse({'error': 'Minimum top-up amount is 100 XAF'}, status=400)
                
            if amount > 1000000:  # Maximum top-up amount
                return JsonResponse({'error': 'Maximum top-up amount is 1,000,000 XAF'}, status=400)
            
            # Validate payment method
            if payment_method not in ['mtn_momo', 'orange_money']:
                return JsonResponse({'error': 'Invalid payment method for top-up'}, status=400)
            
            # Validate phone number for mobile money
            if not phone_number:
                return JsonResponse({'error': 'Phone number is required'}, status=400)
            
            # Clean phone number format
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if not phone_number.startswith('+'):
                phone_number = '+237' + phone_number
            
            with transaction.atomic():
                # Create payment record for top-up
                payment = Payment.objects.create(
                    user=request.user,
                    payment_method=payment_method,
                    amount=amount,
                    phone_number=phone_number,
                    description=f'Wallet top-up for {request.user.get_full_name()}',
                    payment_type='topup'
                )
                
                # Process payment based on method
                if payment_method == 'mtn_momo':
                    result = process_mtn_topup(payment)
                elif payment_method == 'orange_money':
                    result = process_orange_topup(payment)
                else:
                    return JsonResponse({'error': 'Payment method not supported'}, status=400)
                
                if result['success']:
                    return JsonResponse({
                        'success': True,
                        'message': result['message'],
                        'payment_id': str(payment.id),
                        'transaction_id': result.get('transaction_id', ''),
                        'redirect_url': result.get('redirect_url', ''),
                        'requires_approval': result.get('requires_approval', False)
                    })
                else:
                    return JsonResponse({
                        'error': result['message']
                    }, status=400)
                    
        except Exception as e:
            logger.error(f'Top-up processing error: {str(e)}')
            return JsonResponse({'error': 'Top-up processing failed'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def process_mtn_topup(payment):
    """Process MTN Mobile Money top-up"""
    try:
        # Mark payment as processing
        payment.mark_as_processing()
        
        # MTN Mobile Money API integration
        mtn_config = settings.MTN_MOMO_CONFIG
        
        headers = {
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': mtn_config['SUBSCRIPTION_KEY'],
            'Authorization': f'Bearer {get_mtn_access_token()}',
            'X-Reference-Id': str(uuid.uuid4()),
            'X-Target-Environment': 'sandbox'  # Change to 'live' for production
        }
        
        payload = {
            'amount': str(payment.amount),
            'currency': 'XAF',
            'externalId': payment.payment_reference,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': payment.phone_number.replace('+', '')
            },
            'payerMessage': f'Wallet top-up for {payment.user.get_full_name()}',
            'payeeNote': 'Enterprise Canteen Wallet Top-up'
        }
        
        response = requests.post(
            f"{mtn_config['BASE_URL']}/collection/v1_0/requesttopay",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 202:
            # Payment request submitted successfully
            transaction_id = headers['X-Reference-Id']
            payment.transaction_id = transaction_id
            payment.save()
            
            return {
                'success': True,
                'message': 'Top-up request sent. Please approve on your phone.',
                'transaction_id': transaction_id,
                'requires_approval': True
            }
        else:
            error_message = f'MTN API Error: {response.status_code}'
            payment.mark_as_failed(error_message)
            return {
                'success': False,
                'message': 'Failed to initiate MTN top-up'
            }
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return {
            'success': False,
            'message': 'MTN top-up processing failed'
        }


def process_orange_topup(payment):
    """Process Orange Money top-up"""
    try:
        # Mark payment as processing
        payment.mark_as_processing()
        
        # Orange Money API integration
        orange_config = settings.ORANGE_MONEY_CONFIG
        
        # Get access token
        auth_response = requests.post(
            f"{orange_config['BASE_URL']}/oauth/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': orange_config['CLIENT_ID'],
                'client_secret': orange_config['CLIENT_SECRET']
            }
        )
        
        if auth_response.status_code != 200:
            payment.mark_as_failed('Orange authentication failed')
            return {
                'success': False,
                'message': 'Orange Money authentication failed'
            }
        
        access_token = auth_response.json()['access_token']
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        payload = {
            'merchant_key': orange_config['CLIENT_ID'],
            'currency': 'XAF',
            'order_id': payment.payment_reference,
            'amount': int(payment.amount),
            'return_url': orange_config['CALLBACK_URL'],
            'cancel_url': orange_config['CALLBACK_URL'],
            'notif_url': orange_config['CALLBACK_URL'],
            'lang': 'en',
            'reference': f'Wallet top-up for {payment.user.get_full_name()}'
        }
        
        response = requests.post(
            f"{orange_config['BASE_URL']}/webpayment",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 201:
            response_data = response.json()
            payment_url = response_data.get('payment_url')
            transaction_id = response_data.get('pay_token')
            
            payment.transaction_id = transaction_id
            payment.save()
            
            return {
                'success': True,
                'message': 'Redirecting to Orange Money...',
                'transaction_id': transaction_id,
                'redirect_url': payment_url
            }
        else:
            payment.mark_as_failed('Orange API error')
            return {
                'success': False,
                'message': 'Failed to initiate Orange Money top-up'
            }
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return {
            'success': False,
            'message': 'Orange Money top-up processing failed'
        }


@login_required
def process_topup(request):
    """
    Allow employee to top up their wallet balance.
    For now we simulate the topup (e.g., via cash or external payment).
    """

    if request.method == "POST":
        amount = request.POST.get("amount")

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive")

            # Create wallet transaction
            WalletTransaction.objects.create(
                employee=request.user,
                amount=amount,
                transaction_type="credit",
                description="Wallet Top-up",
                created_at=timezone.now(),
            )

            messages.success(request, f"Wallet successfully topped up with {amount} XAF.")
            return redirect("employee_dashboard")

        except Exception as e:
            messages.error(request, f"Invalid amount: {e}")

    return render(request, "employee/process_topup.html")


@login_required
def payment_history(request):
    """Display user payment history"""
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by payment type
    payment_type = request.GET.get('type', 'all')
    if payment_type != 'all':
        payments = payments.filter(payment_type=payment_type)
    
    # Filter by status
    status = request.GET.get('status', 'all')
    if status != 'all':
        payments = payments.filter(status=status)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'payment_type': payment_type,
        'status': status,
    }
    
    return render(request, 'payments/history.html', context)


@login_required
def payment_verification(request, payment_id):
    """Verify payment status"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    if payment.status == 'completed':
        return JsonResponse({
            'status': 'completed',
            'message': 'Payment completed successfully'
        })
    elif payment.status == 'failed':
        return JsonResponse({
            'status': 'failed',
            'message': 'Payment failed'
        })
    elif payment.status == 'processing':
        # Check payment status with provider
        if payment.payment_method == 'mtn_momo':
            result = verify_mtn_payment(payment)
        elif payment.payment_method == 'orange_money':
            result = verify_orange_payment(payment)
        else:
            result = {'status': 'processing'}
        
        return JsonResponse(result)
    else:
        return JsonResponse({
            'status': 'pending',
            'message': 'Payment is pending'
        })


def verify_mtn_payment(payment):
    """Verify MTN Mobile Money payment status"""
    try:
        mtn_config = settings.MTN_MOMO_CONFIG
        
        headers = {
            'Ocp-Apim-Subscription-Key': mtn_config['SUBSCRIPTION_KEY'],
            'Authorization': f'Bearer {get_mtn_access_token()}',
            'X-Target-Environment': 'sandbox'
        }
        
        response = requests.get(
            f"{mtn_config['BASE_URL']}/collection/v1_0/requesttopay/{payment.transaction_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', '').upper()
            
            if status == 'SUCCESSFUL':
                # Process successful payment
                if payment.payment_type == 'topup':
                    complete_wallet_topup(payment)
                payment.mark_as_completed()
                
                return {'status': 'completed', 'message': 'Payment completed successfully'}
            elif status == 'FAILED':
                payment.mark_as_failed('Payment failed by provider')
                return {'status': 'failed', 'message': 'Payment failed'}
            else:
                return {'status': 'processing', 'message': 'Payment is being processed'}
        else:
            return {'status': 'processing', 'message': 'Unable to verify payment status'}
            
    except Exception as e:
        logger.error(f'MTN verification error: {str(e)}')
        return {'status': 'processing', 'message': 'Unable to verify payment status'}


def verify_orange_payment(payment):
    """Verify Orange Money payment status"""
    try:
        orange_config = settings.ORANGE_MONEY_CONFIG
        
        # Get access token
        auth_response = requests.post(
            f"{orange_config['BASE_URL']}/oauth/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': orange_config['CLIENT_ID'],
                'client_secret': orange_config['CLIENT_SECRET']
            }
        )
        
        if auth_response.status_code != 200:
            return {'status': 'processing', 'message': 'Unable to verify payment status'}
        
        access_token = auth_response.json()['access_token']
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(
            f"{orange_config['BASE_URL']}/webpayment/{payment.transaction_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', '').upper()
            
            if status == 'SUCCESS':
                # Process successful payment
                if payment.payment_type == 'topup':
                    complete_wallet_topup(payment)
                payment.mark_as_completed()
                
                return {'status': 'completed', 'message': 'Payment completed successfully'}
            elif status in ['FAILED', 'EXPIRED']:
                payment.mark_as_failed('Payment failed by provider')
                return {'status': 'failed', 'message': 'Payment failed'}
            else:
                return {'status': 'processing', 'message': 'Payment is being processed'}
        else:
            return {'status': 'processing', 'message': 'Unable to verify payment status'}
            
    except Exception as e:
        logger.error(f'Orange verification error: {str(e)}')
        return {'status': 'processing', 'message': 'Unable to verify payment status'}


def complete_wallet_topup(payment):
    """Complete wallet top-up after successful payment"""
    try:
        user = payment.user
        amount = payment.amount
        
        # Add to wallet balance
        old_balance = user.wallet_balance
        user.add_to_wallet(amount)
        
        # Create wallet transaction
        WalletTransaction.objects.create(
            user=user,
            transaction_type='credit',
            source='topup',
            amount=amount,
            balance_before=old_balance,
            balance_after=user.wallet_balance,
            payment=payment,
            description=f'Wallet top-up via {payment.get_payment_method_display()}',
            reference=payment.payment_reference
        )
        
        # Create notification
        Notification.objects.create(
            user=user,
            title='Wallet Top-up Successful',
            message=f'Your wallet has been topped up with {amount} XAF. New balance: {user.wallet_balance} XAF',
            notification_type='payment'
        )
        
        logger.info(f'Wallet top-up completed for user {user.id}: {amount} XAF')
        
    except Exception as e:
        logger.error(f'Wallet top-up completion error: {str(e)}')
        raise


@csrf_exempt
@require_http_methods(["POST"])
def mtn_webhook(request):
    """Handle MTN Mobile Money webhooks"""
    try:
        data = json.loads(request.body)
        
        # Store webhook data
        PaymentWebhook.objects.create(
            provider='mtn',
            event_type=data.get('event_type', 'unknown'),
            data=data
        )
        
        # Process webhook
        reference_id = data.get('reference_id')
        status = data.get('status', '').upper()
        
        if reference_id:
            try:
                payment = Payment.objects.get(transaction_id=reference_id)
                
                if status == 'SUCCESSFUL':
                    if payment.payment_type == 'topup':
                        complete_wallet_topup(payment)
                    payment.mark_as_completed()
                elif status == 'FAILED':
                    payment.mark_as_failed('Payment failed by provider')
                    
            except Payment.DoesNotExist:
                logger.warning(f'Payment not found for MTN webhook: {reference_id}')
        
        return HttpResponse('OK', status=200)
        
    except Exception as e:
        logger.error(f'MTN webhook error: {str(e)}')
        return HttpResponse('Error', status=500)


@csrf_exempt
@require_http_methods(["POST"])
def orange_webhook(request):
    """Handle Orange Money webhooks"""
    try:
        data = json.loads(request.body)
        
        # Store webhook data
        PaymentWebhook.objects.create(
            provider='orange',
            event_type=data.get('event_type', 'unknown'),
            data=data
        )
        
        # Process webhook
        order_id = data.get('order_id')
        status = data.get('status', '').upper()
        
        if order_id:
            try:
                payment = Payment.objects.get(transaction_id=order_id)
                
                if status == 'SUCCESS':
                    if payment.payment_type == 'topup':
                        complete_wallet_topup(payment)
                    payment.mark_as_completed()
                elif status in ['FAILED', 'EXPIRED']:
                    payment.mark_as_failed('Payment failed by provider')
                    
            except Payment.DoesNotExist:
                logger.warning(f'Payment not found for Orange webhook: {order_id}')
        
        return HttpResponse('OK', status=200)
        
    except Exception as e:
        logger.error(f'Orange webhook error: {str(e)}')
        return HttpResponse('Error', status=500)


@login_required
def wallet_dashboard(request):
    """Wallet dashboard for users"""
    user = request.user
    
    # Get recent transactions
    recent_transactions = WalletTransaction.objects.filter(
        user=user
    ).order_by('-created_at')[:10]
    
    # Get wallet statistics
    total_credited = WalletTransaction.objects.filter(
        user=user,
        transaction_type='credit'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    total_debited = WalletTransaction.objects.filter(
        user=user,
        transaction_type='debit'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    context = {
        'wallet_balance': user.wallet_balance,
        'recent_transactions': recent_transactions,
        'total_credited': total_credited,
        'total_debited': total_debited,
    }
    
    return render(request, 'payments/wallet_dashboard.html', context)