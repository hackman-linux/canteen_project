/**
 * Enterprise Canteen System - JavaScript Utilities
 * Complete utility functions for the canteen management system
 */

// Global Configuration
const CanteenConfig = {
    CSRF_TOKEN: document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
    API_ENDPOINTS: {
        CART: '/api/cart/',
        ORDERS: '/api/orders/',
        NOTIFICATIONS: '/api/notifications/',
        MENU: '/api/menu/'
    },
    TOAST_DELAY: 5000,
    POLLING_INTERVAL: 30000 // 30 seconds for real-time updates
};

// Enhanced Print Functions
function printReceipt(orderId, includeQR = false) {
    if (!orderId) {
        showToast('Order ID is required for printing', 'error');
        return;
    }
    
    showLoading(true);
    
    fetch(`/orders/${orderId}/receipt/`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch receipt data');
            return response.json();
        })
        .then(data => {
            const printWindow = window.open('', '_blank');
            const receiptHtml = generateReceiptHTML(data, includeQR);
            
            printWindow.document.write(receiptHtml);
            printWindow.document.close();
            
            printWindow.onload = () => {
                printWindow.print();
                printWindow.onafterprint = () => printWindow.close();
            };
        })
        .catch(error => {
            console.error('Print error:', error);
            showToast('Failed to generate receipt', 'error');
        })
        .finally(() => {
            showLoading(false);
        });
}

function generateReceiptHTML(orderData, includeQR = false) {
    const qrCode = includeQR ? `
        <div class="qr-section">
            <canvas id="qr-code"></canvas>
            <p>Scan for order details</p>
        </div>
    ` : '';
    
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Receipt - Order ${orderData.order_number}</title>
            <style>
                body {
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    line-height: 1.4;
                    max-width: 300px;
                    margin: 0 auto;
                    padding: 10px;
                    background: white;
                }
                .header {
                    text-align: center;
                    border-bottom: 2px solid #333;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                }
                .company-name {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                .order-info {
                    margin: 15px 0;
                }
                .items-table {
                    width: 100%;
                    margin: 15px 0;
                }
                .items-table td {
                    padding: 2px 0;
                    vertical-align: top;
                }
                .item-name {
                    width: 60%;
                }
                .item-qty {
                    width: 15%;
                    text-align: center;
                }
                .item-price {
                    width: 25%;
                    text-align: right;
                }
                .total-section {
                    border-top: 1px solid #333;
                    padding-top: 10px;
                    margin-top: 15px;
                }
                .total-row {
                    display: flex;
                    justify-content: space-between;
                    margin: 3px 0;
                }
                .grand-total {
                    border-top: 1px solid #333;
                    padding-top: 5px;
                    margin-top: 5px;
                    font-weight: bold;
                    font-size: 14px;
                }
                .footer {
                    text-align: center;
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px dashed #333;
                    font-size: 10px;
                }
                .qr-section {
                    text-align: center;
                    margin: 15px 0;
                }
                @media print {
                    body { margin: 0; }
                }
            </style>
        </head>
        <body>
            <div class="header">
                <div class="company-name">ENTERPRISE CANTEEN</div>
                <div>ORDER RECEIPT</div>
            </div>
            
            <div class="order-info">
                <div><strong>Order #:</strong> ${orderData.order_number}</div>
                <div><strong>Date:</strong> ${formatDateTime(orderData.created_at)}</div>
                <div><strong>Customer:</strong> ${orderData.customer_name}</div>
                <div><strong>Office:</strong> ${orderData.office_number || 'N/A'}</div>
                <div><strong>Status:</strong> ${orderData.status.toUpperCase()}</div>
            </div>
            
            <table class="items-table">
                <tr>
                    <td class="item-name"><strong>Item</strong></td>
                    <td class="item-qty"><strong>Qty</strong></td>
                    <td class="item-price"><strong>Price</strong></td>
                </tr>
                ${orderData.items.map(item => `
                    <tr>
                        <td class="item-name">${item.name}</td>
                        <td class="item-qty">${item.quantity}</td>
                        <td class="item-price">${formatCurrency(item.total)}</td>
                    </tr>
                `).join('')}
            </table>
            
            <div class="total-section">
                <div class="total-row">
                    <span>Subtotal:</span>
                    <span>${formatCurrency(orderData.subtotal)}</span>
                </div>
                <div class="total-row">
                    <span>Service Fee:</span>
                    <span>${formatCurrency(orderData.service_fee)}</span>
                </div>
                <div class="total-row grand-total">
                    <span>TOTAL:</span>
                    <span>${formatCurrency(orderData.total_amount)}</span>
                </div>
            </div>
            
            ${qrCode}
            
            <div class="footer">
                <p>Thank you for your order!</p>
                <p>Enterprise Canteen System</p>
                <p>Printed: ${formatDateTime(new Date())}</p>
            </div>
            
            ${includeQR ? `
                <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode/1.5.3/qrcode.min.js"></script>
                <script>
                    QRCode.toCanvas(document.getElementById('qr-code'), 
                        'Order: ${orderData.order_number}\\nTotal: ${formatCurrency(orderData.total_amount)}', 
                        { width: 100, height: 100 }
                    );
                </script>
            ` : ''}
        </body>
        </html>
    `;
}

function printDailySummary() {
    showLoading(true);
    
    fetch('/admin/reports/daily-summary/')
        .then(response => response.json())
        .then(data => {
            const printWindow = window.open('', '_blank');
            printWindow.document.write(generateDailySummaryHTML(data));
            printWindow.document.close();
            printWindow.print();
        })
        .catch(error => {
            console.error('Print error:', error);
            showToast('Failed to generate daily summary', 'error');
        })
        .finally(() => {
            showLoading(false);
        });
}

function generateDailySummaryHTML(data) {
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Daily Summary - ${data.date}</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .stats { display: flex; justify-content: space-around; margin: 20px 0; }
                .stat-box { text-align: center; padding: 15px; border: 1px solid #ddd; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 8px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #f5f5f5; }
                @media print { body { margin: 0; } }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Enterprise Canteen - Daily Summary</h1>
                <h2>${data.date}</h2>
            </div>
            <div class="stats">
                <div class="stat-box">
                    <h3>${data.total_orders}</h3>
                    <p>Total Orders</p>
                </div>
                <div class="stat-box">
                    <h3>${formatCurrency(data.total_revenue)}</h3>
                    <p>Total Revenue</p>
                </div>
                <div class="stat-box">
                    <h3>${data.popular_items.length}</h3>
                    <p>Menu Items Sold</p>
                </div>
            </div>
            <h3>Popular Items</h3>
            <table>
                <tr><th>Item</th><th>Quantity Sold</th><th>Revenue</th></tr>
                ${data.popular_items.map(item => `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.quantity}</td>
                        <td>${formatCurrency(item.revenue)}</td>
                    </tr>
                `).join('')}
            </table>
        </body>
        </html>
    `;
}

// Enhanced Utility Functions
function showLoading(show = true) {
    const body = document.body;
    if (show) {
        body.classList.add('loading');
        // Add loading overlay if it doesn't exist
        if (!document.querySelector('.loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="loading-text">Please wait...</div>
                </div>
            `;
            body.appendChild(overlay);
        }
    } else {
        body.classList.remove('loading');
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
}

function showToast(message, type = 'info', duration = null) {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }

    const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const delay = duration || CanteenConfig.TOAST_DELAY;
    
    // Map types to Bootstrap classes and icons
    const typeConfig = {
        'success': { class: 'text-bg-success', icon: 'bi-check-circle-fill' },
        'error': { class: 'text-bg-danger', icon: 'bi-exclamation-triangle-fill' },
        'warning': { class: 'text-bg-warning', icon: 'bi-exclamation-circle-fill' },
        'info': { class: 'text-bg-info', icon: 'bi-info-circle-fill' },
        'danger': { class: 'text-bg-danger', icon: 'bi-exclamation-triangle-fill' }
    };
    
    const config = typeConfig[type] || typeConfig['info'];
    
    const toastHtml = `
        <div id="${toastId}" class="toast ${config.class}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="bi ${config.icon} me-2"></i>
                <strong class="me-auto">
                    ${type.charAt(0).toUpperCase() + type.slice(1)}
                </strong>
                <small class="text-muted">${formatTime(new Date())}</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay });
    
    toast.show();
    
    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
    
    return toast;
}

// Confirmation Dialog
function showConfirmDialog(message, title = 'Confirm Action', onConfirm = null, onCancel = null) {
    const modalId = 'confirmModal-' + Date.now();
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="${modalId}Label">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="${modalId}Confirm">Confirm</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modalElement = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalElement);
    
    // Handle confirm button
    document.getElementById(modalId + 'Confirm').addEventListener('click', function() {
        if (onConfirm) onConfirm();
        modal.hide();
    });
    
    // Handle modal hidden event
    modalElement.addEventListener('hidden.bs.modal', function() {
        if (onCancel) onCancel();
        modalElement.remove();
    });
    
    modal.show();
    
    return modal;
}

// Format Utilities
function formatCurrency(amount, currency = 'XAF') {
    const numAmount = parseFloat(amount) || 0;
    return `${Math.round(numAmount).toLocaleString()} ${currency}`;
}

function formatDateTime(date) {
    const d = new Date(date);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatTime(date) {
    return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(date) {
    return new Date(date).toLocaleDateString();
}

// API Utilities
async function makeAPICall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CanteenConfig.CSRF_TOKEN
        }
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    if (mergedOptions.headers) {
        mergedOptions.headers = { ...defaultOptions.headers, ...options.headers };
    }
    
    try {
        const response = await fetch(url, mergedOptions);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else {
            return await response.text();
        }
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Session Management
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function updateCSRFToken() {
    const token = getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (token) {
        CanteenConfig.CSRF_TOKEN = token;
    }
}

// Real-time Updates
class RealTimeUpdater {
    constructor() {
        this.pollingInterval = null;
        this.isActive = false;
    }
    
    start(callback, interval = CanteenConfig.POLLING_INTERVAL) {
        if (this.isActive) return;
        
        this.isActive = true;
        this.pollingInterval = setInterval(callback, interval);
        console.log('Real-time updates started');
    }
    
    stop() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
        this.isActive = false;
        console.log('Real-time updates stopped');
    }
    
    restart(callback, interval) {
        this.stop();
        this.start(callback, interval);
    }
}

// Notification Manager
class NotificationManager {
    constructor() {
        this.updater = new RealTimeUpdater();
        this.lastCheckTime = new Date();
    }
    
    init() {
        this.checkPermissions();
        this.startPolling();
        this.setupEventListeners();
    }
    
    checkPermissions() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                console.log('Notification permission:', permission);
            });
        }
    }
    
    startPolling() {
        this.updater.start(() => {
            this.fetchNewNotifications();
        });
    }
    
    async fetchNewNotifications() {
        try {
            const response = await makeAPICall(
                `${CanteenConfig.API_ENDPOINTS.NOTIFICATIONS}new/?since=${this.lastCheckTime.toISOString()}`
            );
            
            if (response.notifications && response.notifications.length > 0) {
                this.handleNewNotifications(response.notifications);
                this.updateBadges(response.unread_count);
            }
            
            this.lastCheckTime = new Date();
        } catch (error) {
            console.error('Failed to fetch notifications:', error);
        }
    }
    
    handleNewNotifications(notifications) {
        notifications.forEach(notification => {
            this.showBrowserNotification(notification);
            this.showToastNotification(notification);
        });
    }
    
    showBrowserNotification(notification) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(notification.title, {
                body: notification.message,
                icon: '/static/img/logo-small.png',
                tag: notification.id
            });
        }
    }
    
    showToastNotification(notification) {
        const type = this.mapNotificationType(notification.type);
        showToast(notification.message, type);
    }
    
    mapNotificationType(type) {
        const mapping = {
            'order_confirmed': 'success',
            'order_ready': 'info',
            'order_cancelled': 'error',
            'payment_successful': 'success',
            'payment_failed': 'error',
            'low_balance': 'warning'
        };
        return mapping[type] || 'info';
    }
    
    updateBadges(count) {
        const badges = document.querySelectorAll('.notification-badge');
        badges.forEach(badge => {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        });
    }
    
    setupEventListeners() {
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.updater.stop();
            } else {
                this.updater.start(() => this.fetchNewNotifications());
            }
        });
        
        // Handle beforeunload
        window.addEventListener('beforeunload', () => {
            this.updater.stop();
        });
    }
}

// Form Validation Utilities
function validateForm(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    const errors = [];
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            errors.push(`${field.name || field.id} is required`);
            field.classList.add('is-invalid');
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    // Email validation
    const emailFields = formElement.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            isValid = false;
            errors.push('Please enter a valid email address');
            field.classList.add('is-invalid');
        }
    });
    
    return { isValid, errors };
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Initialize Global Styles and Components
function initializeGlobalStyles() {
    // Add enhanced loading overlay styles
    const styles = `
        <style id="canteen-global-styles">
            .loading-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.9);
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                z-index: 10000;
            }
            
            .loading-spinner {
                text-align: center;
            }
            
            .loading-text {
                margin-top: 15px;
                font-size: 14px;
                color: #6c757d;
            }
            
            .toast {
                min-width: 300px;
                box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.1);
            }
            
            .toast-container {
                max-height: 100vh;
                overflow-y: auto;
            }
            
            .notification-badge {
                position: absolute;
                top: -5px;
                right: -5px;
                background: #dc3545;
                color: white;
                border-radius: 50%;
                padding: 2px 6px;
                font-size: 12px;
                min-width: 20px;
                text-align: center;
            }
            
            .fade-in {
                animation: fadeIn 0.3s ease-in;
            }
            
            .fade-out {
                animation: fadeOut 0.3s ease-out;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; transform: translateY(0); }
                to { opacity: 0; transform: translateY(-10px); }
            }
            
            .pulse {
                animation: pulse 1.5s infinite;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            
            @media (max-width: 768px) {
                .toast-container {
                    width: 100%;
                    padding: 0.5rem;
                }
                
                .toast {
                    min-width: auto;
                    width: 100%;
                }
            }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', styles);
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Update CSRF token
    updateCSRFToken();
    
    // Initialize global styles
    initializeGlobalStyles();
    
    // Initialize notification manager
    const notificationManager = new NotificationManager();
    notificationManager.init();
    
    // Make global utilities available
    window.CanteenUtils = {
        showLoading,
        showToast,
        showConfirmDialog,
        makeAPICall,
        formatCurrency,
        formatDateTime,
        printReceipt,
        printDailySummary,
        validateForm,
        updateCSRFToken,
        NotificationManager: notificationManager
    };
    
    console.log('Canteen System utilities initialized');
});

// Export for ES6 modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showLoading,
        showToast,
        showConfirmDialog,
        makeAPICall,
        formatCurrency,
        formatDateTime,
        printReceipt,
        printDailySummary,
        NotificationManager
    };
}