import csv
import json
import uuid
import logging
from decimal import Decimal
from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, Avg, F
from django.core.paginator import Paginator
from django.conf import settings

from .models import Report, DailySalesReport
from apps.orders.models import Order, OrderItem
from apps.menu.models import MenuItem, MenuCategory
from apps.payments.models import Payment, WalletTransaction
from apps.authentication.models import User

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Reports Management Views
# ----------------------------------------------------------------------

@login_required
def reports_list(request):
    """List all generated reports"""
    if not (request.user.is_canteen_admin() or request.user.is_system_admin()):
        return redirect('dashboard_redirect')

    reports = Report.objects.all().select_related('generated_by').order_by('-created_at')

    # Filter by type
    report_type = request.GET.get('type', 'all')
    if report_type != 'all':
        reports = reports.filter(report_type=report_type)

    # Search
    search = request.GET.get('search', '').strip()
    if search:
        reports = reports.filter(Q(title__icontains=search) | Q(report_type__icontains=search))

    # Pagination
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'report_type': report_type,
        'search': search,
        'report_types': Report.REPORT_TYPES
    }

    return render(request, 'reports/list.html', context)


@login_required
def report_details(request, report_id):
    """View report details"""
    if not (request.user.is_canteen_admin() or request.user.is_system_admin()):
        return redirect('dashboard_redirect')

    report = get_object_or_404(Report, id=report_id)
    return render(request, 'reports/details.html', {'report': report})


@login_required
def download_report(request, report_id):
    """Download report as CSV"""
    if not (request.user.is_canteen_admin() or request.user.is_system_admin()):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    report = get_object_or_404(Report, id=report_id)

    if report.report_type == 'sales':
        return generate_sales_csv(report.data, report.parameters['start_date'], report.parameters['end_date'])
    elif report.report_type == 'menu_performance':
        return generate_menu_performance_csv(report.data, report.parameters['start_date'], report.parameters['end_date'])
    elif report.report_type == 'user_activity':
        return generate_user_activity_csv(report.data, report.parameters['start_date'], report.parameters['end_date'])
    elif report.report_type == 'financial':
        return generate_financial_csv(report.data, report.parameters['start_date'], report.parameters['end_date'])
    elif report.report_type == 'inventory':
        return generate_inventory_csv(report.data)
    elif report.report_type == 'customer_analytics':
        return generate_customer_analytics_csv(report.data, report.parameters['start_date'], report.parameters['end_date'])
    else:
        return JsonResponse({'error': 'Report type not supported for download'}, status=400)


@login_required
def delete_report(request, report_id):
    """Delete a report"""
    if not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method == 'DELETE':
        try:
            report = get_object_or_404(Report, id=report_id)
            report_title = report.title
            report.delete()
            return JsonResponse({'success': True, 'message': f'Report "{report_title}" deleted successfully'})
        except Exception as e:
            return JsonResponse({'error': f'Error deleting report: {str(e)}'}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ----------------------------------------------------------------------
# CSV Generators
# ----------------------------------------------------------------------

def generate_sales_csv(report_data, start_date, end_date):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Sales Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Order ID', 'Customer', 'Total Amount', 'Status', 'Created At'])
    for order in report_data['orders']:
        writer.writerow([order['id'], order['customer'], order['total'], order['status'], order['created_at']])
    return response


def generate_menu_performance_csv(report_data, start_date, end_date):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="menu_performance_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Menu Performance Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Item Name', 'Category', 'Total Orders', 'Total Quantity', 'Total Revenue (XAF)', 'Average Rating', 'Current Stock'])
    for item in report_data['menu_items']:
        writer.writerow([item['name'], item['category'], item['total_orders'], item['total_quantity'], item['total_revenue'], item['average_rating'], item['current_stock']])
    return response


def generate_user_activity_csv(report_data, start_date, end_date):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="user_activity_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['User Activity Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Name', 'Email', 'Role', 'Orders Count', 'Total Spent (XAF)'])
    for user in report_data['user_orders']:
        writer.writerow([user['name'], user['email'], user['role'], user['orders_count'], user['total_spent']])
    return response


def generate_financial_csv(report_data, start_date, end_date):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="financial_report_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Financial Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Total Revenue (XAF)', report_data['summary']['total_revenue']])
    writer.writerow(['Total Payments', report_data['summary']['total_payments']])
    writer.writerow(['Total Refunds (XAF)', report_data['summary']['total_refunds']])
    writer.writerow(['Net Revenue (XAF)', report_data['summary']['net_revenue']])
    writer.writerow(['Wallet Credits (XAF)', report_data['summary']['wallet_credits']])
    writer.writerow(['Wallet Debits (XAF)', report_data['summary']['wallet_debits']])
    return response


def generate_inventory_csv(report_data):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="inventory_report_{datetime.now().strftime("%Y%m%d")}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Inventory Report'])
    writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    writer.writerow(['Item Name', 'Category', 'Current Stock', 'Low Stock Threshold', 'Price (XAF)', 'Inventory Value (XAF)', 'Status', 'Orders (30 days)'])
    for item in report_data['stock_details']:
        writer.writerow([item['name'], item['category'], item['current_stock'], item['low_stock_threshold'], item['price'], item['inventory_value'], item['status'], item['orders_last_30_days']])
    return response


def generate_customer_analytics_csv(report_data, start_date, end_date):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="customer_analytics_{start_date}_to_{end_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Customer Analytics Report'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Name', 'Email', 'Orders Count', 'Total Spent (XAF)', 'Avg Order Value (XAF)', 'Wallet Balance (XAF)'])
    for customer in report_data['top_customers']:
        writer.writerow([customer['name'], customer['email'], customer['orders_count'], customer['total_spent'], customer['avg_order_value'], customer['wallet_balance']])
    return response

# ----------------------------------------------------------------------
# Note: All report generators are now standardized and arranged properly.
# ----------------------------------------------------------------------
