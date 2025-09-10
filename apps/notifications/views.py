from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, F
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import json
import logging

from .models import Notification
from apps.authentication.models import User

logger = logging.getLogger(__name__)

@login_required
def notifications_list(request):
    """Display user's notifications"""
    # Get user's notifications
    notifications = UserNotification.objects.filter(
        user=request.user
    ).select_related('notification').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status', 'all')
    if status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by type
    notification_type = request.GET.get('type', 'all')
    if notification_type != 'all':
        notifications = notifications.filter(notification__notification_type=notification_type)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts
    unread_count = UserNotification.objects.filter(
        user=request.user, is_read=False
    ).count()
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'notification_type': notification_type,
        'unread_count': unread_count,
        'notification_types': dict(Notification.NOTIFICATION_TYPE_CHOICES)

    }
    
    return render(request, 'notifications/list.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    if request.method == 'POST':
        try:
            user_notification = get_object_or_404(
                UserNotification, 
                id=notification_id, 
                user=request.user
            )
            
            user_notification.mark_as_read()
            
            return JsonResponse({
                'success': True,
                'message': 'Notification marked as read'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error marking notification as read: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        try:
            UserNotification.objects.filter(
                user=request.user,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
            
            return JsonResponse({
                'success': True,
                'message': 'All notifications marked as read'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error marking notifications as read: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def delete_notification(request, notification_id):
    """Delete a notification"""
    if request.method == 'DELETE':
        try:
            user_notification = get_object_or_404(
                UserNotification, 
                id=notification_id, 
                user=request.user
            )
            
            user_notification.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Notification deleted'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error deleting notification: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)




# @login_required
# def notifications_api(request):
#     """API endpoint for user notifications"""
#     # Get recent notifications
#     notifications = UserNotification.objects.filter(
#         user=request.user
#     ).select_related('notification').order_by('-created_at')[:10]
    
#     notifications_data = []
#     for user_notification in notifications:
#         notification = user_notification.notification
#         notifications_data.append({
#             'id': str(user_notification.id),
#             'title': notification.title,
#             'message': notification.message,
#             'type': notification.notification_type,
#             'is_read': user_notification.is_read,
#             'created_at': user_notification.created_at.strftime('%b %d, %Y at %I:%M %p'),
#             'priority': notification.priority,
#             'action_url': notification.action_url,
#             'action_text': notification.action_text
#         })
    
#     # Get unread count
#     unread_count = UserNotification.objects.filter(
#         user=request.user, is_read=False
#     ).count()
    
#     return JsonResponse({
#         'notifications': notifications_data,
#         'unread_count': unread_count
#     })


@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    user = request.user
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Get or create preferences
            preferences, created = NotificationPreference.objects.get_or_create(
                user=user,
                defaults={
                    'email_enabled': True,
                    'push_enabled': True,
                    'order_notifications': True,
                    'payment_notifications': True,
                    'menu_notifications': True,
                    'system_notifications': True
                }
            )
            
            # Update preferences
            preferences.email_enabled = data.get('email_enabled', preferences.email_enabled)
            preferences.push_enabled = data.get('push_enabled', preferences.push_enabled)
            preferences.order_notifications = data.get('order_notifications', preferences.order_notifications)
            preferences.payment_notifications = data.get('payment_notifications', preferences.payment_notifications)
            preferences.menu_notifications = data.get('menu_notifications', preferences.menu_notifications)
            preferences.system_notifications = data.get('system_notifications', preferences.system_notifications)
            preferences.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Notification preferences updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error updating preferences: {str(e)}'
            }, status=400)
    
    else:
        # GET request - display preferences
        try:
            preferences = NotificationPreference.objects.get(user=user)
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            preferences = NotificationPreference.objects.create(
                user=user,
                email_enabled=True,
                push_enabled=True,
                order_notifications=True,
                payment_notifications=True,
                menu_notifications=True,
                system_notifications=True
            )
        
        context = {
            'preferences': preferences
        }
        
        return render(request, 'notifications/preferences.html', context)


def send_notification(user, title, message, notification_type='info', priority='normal', action_url=None, action_text=None):
    """Send notification to a user"""
    try:
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            action_url=action_url,
            action_text=action_text
        )
        
        # Create user notification
        user_notification = UserNotification.objects.create(
            user=user,
            notification=notification
        )
        
        # Check user preferences
        try:
            preferences = NotificationPreference.objects.get(user=user)
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            preferences = NotificationPreference.objects.create(
                user=user,
                email_enabled=True,
                push_enabled=True,
                order_notifications=True,
                payment_notifications=True,
                menu_notifications=True,
                system_notifications=True
            )
        
        # Check if user wants this type of notification
        should_send = True
        if notification_type == 'order' and not preferences.order_notifications:
            should_send = False
        elif notification_type == 'payment' and not preferences.payment_notifications:
            should_send = False
        elif notification_type == 'menu' and not preferences.menu_notifications:
            should_send = False
        elif notification_type == 'system' and not preferences.system_notifications:
            should_send = False
        
        if should_send:
            # Send email notification if enabled
            if preferences.email_enabled and user.email:
                send_email_notification(user, notification)
            
            # TODO: Implement push notifications when mobile app is ready
            if preferences.push_enabled:
                # Placeholder for push notification
                pass
        
        return user_notification
        
    except Exception as e:
        logger.error(f'Error sending notification to user {user.id}: {str(e)}')
        return None


def send_email_notification(user, notification):
    """Send email notification"""
    try:
        # Get email template
        try:
            template = NotificationTemplate.objects.get(
                name=f'email_{notification.notification_type}',
                is_active=True
            )
            subject = template.subject
            html_content = template.render_content({
                'user': user,
                'notification': notification,
                'site_name': 'Enterprise Canteen'
            })
        except NotificationTemplate.DoesNotExist:
            # Use default template
            subject = f'Enterprise Canteen - {notification.title}'
            html_content = render_to_string('notifications/email_template.html', {
                'user': user,
                'notification': notification,
                'site_name': 'Enterprise Canteen'
            })
        
        # Convert to plain text
        plain_message = strip_tags(html_content)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False
        )
        
        logger.info(f'Email notification sent to {user.email}')
        
    except Exception as e:
        logger.error(f'Error sending email notification: {str(e)}')


def send_bulk_notification(users, title, message, notification_type='info', priority='normal'):
    """Send notification to multiple users"""
    try:
        notifications_created = 0
        
        for user in users:
            user_notification = send_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
            if user_notification:
                notifications_created += 1
        
        logger.info(f'Bulk notification sent to {notifications_created} users')
        return notifications_created
        
    except Exception as e:
        logger.error(f'Error sending bulk notification: {str(e)}')
        return 0


class SystemNotificationManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """System admin notification management"""
    template_name = 'notifications/system_management.html'
    
    def test_func(self):
        return self.request.user.is_system_admin() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Notification statistics
        total_notifications = Notification.objects.count()
        unread_notifications = UserNotification.objects.filter(is_read=False).count()
        today_notifications = Notification.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        context.update({
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'today_notifications': today_notifications,
        })
        
        # Recent notifications
        recent_notifications = Notification.objects.select_related('user').order_by('-created_at')[:10]
        context['recent_notifications'] = recent_notifications
        
        # Notification templates
        templates = NotificationTemplate.objects.filter(is_active=True)
        context['templates'] = templates
        
        return context


@login_required
def system_notification_management(request):
    """System notification management view"""
    if not request.user.is_system_admin():
        return redirect('dashboard_redirect')
    
    view = SystemNotificationManagementView.as_view()
    return view(request)


@login_required
def send_system_notification(request):
    """Send system-wide notification"""
    if not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            title = data.get('title', '').strip()
            message = data.get('message', '').strip()
            notification_type = data.get('type', 'system')
            priority = data.get('priority', 'normal')
            target_users = data.get('target_users', 'all')
            
            if not title or not message:
                return JsonResponse({'error': 'Title and message are required'}, status=400)
            
            # Get target users
            if target_users == 'all':
                users = User.objects.filter(is_active=True)
            elif target_users == 'employees':
                users = User.objects.filter(role='employee', is_active=True)
            elif target_users == 'admins':
                users = User.objects.filter(role__in=['canteen_admin', 'system_admin'], is_active=True)
            else:
                return JsonResponse({'error': 'Invalid target users'}, status=400)
            
            # Send bulk notification
            sent_count = send_bulk_notification(
                users=users,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Notification sent to {sent_count} users',
                'sent_count': sent_count
            })
            
        except Exception as e:
            logger.error(f'Error sending system notification: {str(e)}')
            return JsonResponse({
                'error': 'Failed to send notification'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def notification_templates_api(request):
    """API endpoint for notification templates"""
    if not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    templates = NotificationTemplate.objects.filter(is_active=True).order_by('name')
    
    templates_data = []
    for template in templates:
        templates_data.append({
            'id': str(template.id),
            'name': template.name,
            'subject': template.subject,
            'content': template.content,
            'variables': template.variables,
            'notification_type': template.notification_type
        })
    
    return JsonResponse({'templates': templates_data})


@login_required
def create_notification_template(request):
    """Create a new notification template"""
    if not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            template = NotificationTemplate.objects.create(
                name=data['name'],
                subject=data['subject'],
                content=data['content'],
                notification_type=data.get('notification_type', 'system'),
                variables=data.get('variables', []),
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Template created successfully',
                'template_id': str(template.id)
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error creating template: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def send_order_notification(order, notification_type, additional_context=None):
    """Send order-related notifications"""
    try:
        user = order.customer
        context = {
            'order': order,
            'user': user,
            'order_number': order.order_number,
            'total_amount': order.total_amount,
            'status': order.get_status_display(),
        }
        
        if additional_context:
            context.update(additional_context)
        
        # Notification messages based on type
        if notification_type == 'order_confirmed':
            title = 'Order Confirmed'
            message = f'Your order #{order.order_number} has been confirmed and is being prepared.'
            action_url = f'/orders/{order.id}/details/'
            action_text = 'View Order'
        elif notification_type == 'order_ready':
            title = 'Order Ready'
            message = f'Your order #{order.order_number} is ready for pickup!'
            action_url = f'/orders/{order.id}/details/'
            action_text = 'View Order'
        elif notification_type == 'order_cancelled':
            title = 'Order Cancelled'
            message = f'Your order #{order.order_number} has been cancelled.'
            action_url = f'/orders/{order.id}/details/'
            action_text = 'View Details'
        elif notification_type == 'order_delayed':
            title = 'Order Delayed'
            message = f'Your order #{order.order_number} is taking longer than expected. We apologize for the delay.'
            action_url = f'/orders/{order.id}/details/'
            action_text = 'View Order'
        else:
            title = 'Order Update'
            message = f'Your order #{order.order_number} status has been updated.'
            action_url = f'/orders/{order.id}/details/'
            action_text = 'View Order'
        
        # Send notification
        return send_notification(
            user=user,
            title=title,
            message=message,
            notification_type='order',
            action_url=action_url,
            action_text=action_text
        )
        
    except Exception as e:
        logger.error(f'Error sending order notification: {str(e)}')
        return None


def send_payment_notification(payment, notification_type):
    """Send payment-related notifications"""
    try:
        user = payment.user
        
        if notification_type == 'payment_successful':
            if payment.payment_type == 'topup':
                title = 'Wallet Top-up Successful'
                message = f'Your wallet has been topped up with {payment.amount} XAF via {payment.get_payment_method_display()}.'
            else:
                title = 'Payment Successful'
                message = f'Payment of {payment.amount} XAF for order #{payment.order.order_number} completed successfully.'
            action_url = '/payments/history/'
            action_text = 'View Payment History'
            
        elif notification_type == 'payment_failed':
            if payment.payment_type == 'topup':
                title = 'Wallet Top-up Failed'
                message = f'Your wallet top-up of {payment.amount} XAF failed. Please try again.'
            else:
                title = 'Payment Failed'
                message = f'Payment of {payment.amount} XAF for order #{payment.order.order_number} failed.'
            action_url = '/payments/history/'
            action_text = 'Try Again'
            
        elif notification_type == 'low_balance':
            title = 'Low Wallet Balance'
            message = f'Your wallet balance is low ({user.wallet_balance} XAF). Consider topping up your wallet.'
            action_url = '/payments/topup/'
            action_text = 'Top Up Wallet'
            
        else:
            title = 'Payment Update'
            message = f'Payment status updated for {payment.amount} XAF.'
            action_url = '/payments/history/'
            action_text = 'View Details'
        
        # Send notification
        return send_notification(
            user=user,
            title=title,
            message=message,
            notification_type='payment',
            action_url=action_url,
            action_text=action_text
        )
        
    except Exception as e:
        logger.error(f'Error sending payment notification: {str(e)}')
        return None


def send_menu_notification(users, notification_type, additional_context=None):
    """Send menu-related notifications"""
    try:
        context = additional_context or {}
        
        if notification_type == 'daily_menu_updated':
            title = 'New Daily Menu Available'
            message = "Today's special menu has been updated with new items and offers!"
            action_url = '/menu/'
            action_text = 'View Menu'
            
        elif notification_type == 'new_item_added':
            item_name = context.get('item_name', 'new item')
            title = 'New Menu Item'
            message = f'Check out our new menu item: {item_name}!'
            action_url = '/menu/'
            action_text = 'View Menu'
            
        elif notification_type == 'special_offer':
            title = 'Special Offer Available'
            message = context.get('message', 'Limited time special offers available!')
            action_url = '/menu/'
            action_text = 'View Offers'
            
        else:
            title = 'Menu Update'
            message = 'The menu has been updated with new items and changes.'
            action_url = '/menu/'
            action_text = 'View Menu'
        
        # Send to multiple users
        sent_count = 0
        for user in users:
            user_notification = send_notification(
                user=user,
                title=title,
                message=message,
                notification_type='menu',
                action_url=action_url,
                action_text=action_text
            )
            if user_notification:
                sent_count += 1
        
        return sent_count
        
    except Exception as e:
        logger.error(f'Error sending menu notifications: {str(e)}')
        return 0


@login_required
def get_real_time_notifications(request):
    """Get real-time notifications for AJAX polling"""
    # Get notifications created in the last 5 minutes
    five_minutes_ago = timezone.now() - timezone.timedelta(minutes=5)
    
    recent_notifications = UserNotification.objects.filter(
        user=request.user,
        created_at__gte=five_minutes_ago,
        is_read=False
    ).select_related('notification').order_by('-created_at')
    
    notifications_data = []
    for user_notification in recent_notifications:
        notification = user_notification.notification
        notifications_data.append({
            'id': str(user_notification.id),
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'priority': notification.priority,
            'created_at': user_notification.created_at.isoformat(),
            'action_url': notification.action_url,
            'action_text': notification.action_text
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'count': len(notifications_data)
    })


@login_required
def notification_stats_api(request):
    """API endpoint for notification statistics"""
    if not request.user.is_canteen_admin() and not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Overall statistics
    total_notifications = Notification.objects.count()
    unread_notifications = UserNotification.objects.filter(is_read=False).count()
    
    # Today's statistics
    today = timezone.now().date()
    today_notifications = Notification.objects.filter(created_at__date=today).count()
    
    # Notifications by type
    notifications_by_type = Notification.objects.values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent activity
    recent_activity = Notification.objects.select_related('user').order_by('-created_at')[:5]
    
    recent_data = []
    for notification in recent_activity:
        recent_data.append({
            'title': notification.title,
            'user': notification.user.get_full_name() if notification.user else 'System',
            'type': notification.notification_type,
            'created_at': notification.created_at.strftime('%b %d, %Y at %I:%M %p')
        })
    
    return JsonResponse({
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'today_notifications': today_notifications,
        'notifications_by_type': list(notifications_by_type),
        'recent_activity': recent_data
    })