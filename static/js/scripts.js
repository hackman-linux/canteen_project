// Ensure CSRF token is included in AJAX POST requests
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
const csrftoken = getCookie('csrftoken');

// Helper function to make AJAX requests
function makeAjaxRequest(url, method, data, successCallback, errorCallback) {
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: method === 'POST' ? JSON.stringify(data) : null
    })
    .then(response => response.json())
    .then(data => successCallback(data))
    .catch(error => errorCallback(error));
}

// Order History Page
document.addEventListener('DOMContentLoaded', () => {
    // New Order Button - redirects to menu
    const newOrderBtn = document.querySelector('.new-order-btn');
    if (newOrderBtn) {
        newOrderBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = '{% url "menu:employee_menu" %}';
        });
    }

    // Load More Orders - uses existing pagination logic
    const loadMoreOrdersBtn = document.querySelector('.load-more-orders');
    if (loadMoreOrdersBtn) {
        loadMoreOrdersBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const limit = document.querySelectorAll('.order-item').length;
            makeAjaxRequest(`/orders/history/?limit=${limit}`, 'GET', null,
                (data) => {
                    const ordersContainer = document.querySelector('.orders-container');
                    ordersContainer.insertAdjacentHTML('beforeend', data.orders_html);
                    if (!data.has_more_orders) {
                        loadMoreOrdersBtn.remove();
                    }
                },
                (error) => console.error('Error loading more orders:', error)
            );
        });
    }

    // Filter and Sort - update order_history view to handle GET params
    const timePeriodSelect = document.querySelector('select[name="time_period"]');
    const statusSelect = document.querySelector('select[name="status"]');
    const sortSelect = document.querySelector('select[name="sort"]');
    const applyFilters = () => {
        const timePeriod = timePeriodSelect ? timePeriodSelect.value : '';
        const status = statusSelect ? statusSelect.value : '';
        const sort = sortSelect ? sortSelect.value : '';
        window.location.href = `/orders/history/?time_period=${timePeriod}&status=${status}&sort=${sort}`;
    };
    if (timePeriodSelect) timePeriodSelect.addEventListener('change', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (sortSelect) sortSelect.addEventListener('change', applyFilters);

    // Order Actions
    document.querySelectorAll('.order-actions a').forEach(actionBtn => {
        actionBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const action = e.target.getAttribute('data-action');
            const orderId = e.target.getAttribute('data-order-id');
            if (action === 'details') {
                window.location.href = `/orders/${orderId}/detail/`;
            } else if (action === 'reorder') {
                // Implement reorder via POST to new endpoint
                makeAjaxRequest(`/orders/${orderId}/reorder/`, 'POST', {},
                    (data) => {
                        alert('Reorder initiated. Redirecting to menu.');
                        window.location.href = '{% url "menu:employee_menu" %}';
                    },
                    (error) => console.error('Error reordering:', error)
                );
            } else if (action === 'cancel') {
                if (confirm('Are you sure you want to cancel this order?')) {
                    makeAjaxRequest(`/orders/${orderId}/cancel/`, 'POST', {},
                        (data) => {
                            e.target.closest('.order-item').remove();
                            alert('Order cancelled successfully.');
                        },
                        (error) => console.error('Error cancelling order:', error)
                    );
                }
            } else if (action === 'receipt') {
                window.location.href = `/orders/${orderId}/receipt/`;
            }
        });
    });
});

// Notifications Page
document.addEventListener('DOMContentLoaded', () => {
    // Mark All as Read - uses existing mark_all_read view
    const markAllReadBtn = document.querySelector('.mark-all-read');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            makeAjaxRequest('/notifications/mark-all-read/', 'POST', {},
                (data) => {
                    document.querySelectorAll('.unread-indicator').forEach(ind => ind.remove());
                    document.querySelector('.unread-count').textContent = '0';
                    alert('All notifications marked as read.');
                },
                (error) => console.error('Error marking all as read:', error)
            );
        });
    }

    // Refresh Notifications - uses notifications_api
    const refreshBtn = document.querySelector('.refresh-notifications');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', (e) => {
            e.preventDefault();
            makeAjaxRequest('/notifications/api/', 'GET', null,
                (data) => {
                    const container = document.querySelector('.notifications-container');
                    container.innerHTML = ''; // Clear existing
                    data.notifications.forEach(notif => {
                        const item = createNotificationItem(notif);
                        container.appendChild(item);
                    });
                },
                (error) => console.error('Error refreshing notifications:', error)
            );
        });
    }

    // Filter - update notifications_list to handle GET params
    const typeSelect = document.querySelector('select[name="notification_type"]');
    const statusSelect = document.querySelector('select[name="notification_status"]');
    const timeSelect = document.querySelector('select[name="notification_time"]');
    const applyFilters = () => {
        const type = typeSelect ? typeSelect.value : '';
        const status = statusSelect ? statusSelect.value : '';
        const time = timeSelect ? timeSelect.value : '';
        window.location.href = `/notifications/?type=${type}&status=${status}&time=${time}`;
    };
    if (typeSelect) typeSelect.addEventListener('change', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (timeSelect) timeSelect.addEventListener('change', applyFilters);

    // Load More - add endpoint
    const loadMoreBtn = document.querySelector('.load-more-notifications');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const offset = document.querySelectorAll('.notification-item').length;
            makeAjaxRequest(`/notifications/load-more/?offset=${offset}`, 'GET', null,
                (data) => {
                    const container = document.querySelector('.notifications-container');
                    data.notifications.forEach(notif => {
                        const item = createNotificationItem(notif);
                        container.appendChild(item);
                    });
                    if (!data.has_more) {
                        loadMoreBtn.remove();
                    }
                },
                (error) => console.error('Error loading more:', error)
            );
        });
    }

    // Notification click - mark read and view details
    document.addEventListener('click', (e) => {
        if (e.target.closest('.notification-item')) {
            const item = e.target.closest('.notification-item');
            const notifId = item.getAttribute('data-id');
            if (!item.classList.contains('read')) {
                makeAjaxRequest(`/notifications/${notifId}/read/`, 'POST', {},
                    (data) => {
                        item.classList.add('read');
                        item.querySelector('.unread-indicator')?.remove();
                    },
                    (error) => console.error('Error marking read:', error)
                );
            }
            const actionUrl = item.querySelector('.action-link')?.href;
            if (actionUrl && !e.target.closest('.action-link')) {
                window.location.href = actionUrl;
            }
        }
    });

    function createNotificationItem(notif) {
        // Dynamic creation based on template structure
        const div = document.createElement('div');
        div.className = `notification-item ${notif.is_read ? 'read' : 'unread'}`;
        div.setAttribute('data-id', notif.id);
        div.innerHTML = `
            <div class="notification-icon">
                ${notif.type === 'order' ? '📦' : notif.type === 'system' ? '⚙️' : '📢'}
            </div>
            <div class="notification-content">
                <div class="notification-header">
                    <h3>${notif.title}</h3>
                    <span class="timestamp">${notif.created_at} ago</span>
                    ${!notif.is_read ? '<span class="unread-indicator">•</span>' : ''}
                    <span class="notification-badge">${notif.type}</span>
                </div>
                <p>${notif.message}</p>
                ${notif.action_url ? `<a href="${notif.action_url}" class="action-link btn">View Details</a>` : ''}
            </div>
        `;
        return div;
    }
});

// Menu Page
document.addEventListener('DOMContentLoaded', () => {
    let cart = JSON.parse(localStorage.getItem('cart') || '[]');

    const updateCartDisplay = () => {
        const cartCount = document.querySelector('.cart-count');
        const cartItemsContainer = document.querySelector('.cart-items');
        const subtotalEl = document.querySelector('.cart-subtotal');
        const serviceFeeEl = document.querySelector('.cart-service-fee');
        const totalEl = document.querySelector('.cart-total');
        const emptyCartMsg = document.querySelector('.empty-cart-message');

        if (cart.length === 0) {
            emptyCartMsg.style.display = 'block';
            cartItemsContainer.innerHTML = '';
        } else {
            emptyCartMsg.style.display = 'none';
            cartItemsContainer.innerHTML = cart.map(item => `
                <div class="cart-item-row">
                    <span>${item.name} × ${item.quantity}</span>
                    <span>${(item.price * item.quantity).toFixed(0)} XAF</span>
                    <button class="remove-item" data-id="${item.id}">Remove</button>
                </div>
            `).join('');
        }

        const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
        const serviceFee = subtotal * 0.05;
        const total = subtotal + serviceFee;

        if (cartCount) cartCount.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);
        if (subtotalEl) subtotalEl.textContent = `${subtotal.toFixed(0)} XAF`;
        if (serviceFeeEl) serviceFeeEl.textContent = `${serviceFee.toFixed(0)} XAF`;
        if (totalEl) totalEl.textContent = `${total.toFixed(0)} XAF`;

        localStorage.setItem('cart', JSON.stringify(cart));
    };

    // Add to Cart
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const itemId = btn.getAttribute('data-item-id');
            const nameEl = btn.closest('.menu-item').querySelector('.item-name');
            const priceEl = btn.closest('.menu-item').querySelector('.item-price');
            const qtyInput = btn.previousElementSibling; // assume quantity input before button
            const quantity = parseInt(qtyInput ? qtyInput.value : 1);
            const name = nameEl ? nameEl.textContent.trim() : 'Item';
            const price = parseFloat(priceEl ? priceEl.textContent.replace(/[^\d.]/g, '') : 0);

            if (quantity > 0 && price > 0) {
                const existing = cart.find(item => item.id == itemId);
                if (existing) {
                    existing.quantity += quantity;
                } else {
                    cart.push({ id: itemId, name, price, quantity });
                }
                updateCartDisplay();
                alert(`${quantity} × ${name} added to cart!`);
            }
        });
    });

    // Remove from Cart
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-item')) {
            const itemId = e.target.getAttribute('data-id');
            cart = cart.filter(item => item.id != itemId);
            updateCartDisplay();
        }
    });

    // Clear Cart
    const clearCartBtn = document.querySelector('.clear-cart');
    if (clearCartBtn) {
        clearCartBtn.addEventListener('click', () => {
            cart = [];
            updateCartDisplay();
            alert('Cart cleared!');
        });
    }

    // Create Order - uses place_order view
    const createOrderBtns = document.querySelectorAll('.create-order');
    createOrderBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (cart.length === 0) {
                alert('Your cart is empty!');
                return;
            }
            // Redirect to place_order with cart in session or POST
            // For simplicity, set session via AJAX or redirect with params
            makeAjaxRequest('/orders/place/', 'POST', { cart: cart },
                (data) => {
                    if (data.success) {
                        cart = [];
                        updateCartDisplay();
                        window.location.href = `/orders/${data.order_id}/`;
                    }
                },
                (error) => console.error('Error creating order:', error)
            );
        });
    });

    // View Cart - toggle visibility
    const viewCartBtn = document.querySelector('.view-cart');
    if (viewCartBtn) {
        viewCartBtn.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelector('.cart-section').classList.toggle('hidden');
        });
    }

    // Refresh Menu - reload page or AJAX
    const refreshMenuBtn = document.querySelector('.refresh-menu');
    if (refreshMenuBtn) {
        refreshMenuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.reload();
        });
    }

    updateCartDisplay();
});

// Dashboard Page
document.addEventListener('DOMContentLoaded', () => {
    // Quick Order & Today's Menu & Browse Menu - redirect to menu
    const quickOrderBtn = document.querySelector('.quick-order');
    const todaysMenuBtn = document.querySelector('.todays-menu');
    const browseMenuBtn = document.querySelector('.browse-menu');
    [quickOrderBtn, todaysMenuBtn, browseMenuBtn].forEach(btn => {
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '{% url "menu:employee_menu" %}';
            });
        }
    });

    // Reorder Last Meal - find last order and reorder
    const reorderLastBtn = document.querySelector('.reorder-last');
    if (reorderLastBtn) {
        reorderLastBtn.addEventListener('click', (e) => {
            e.preventDefault();
            makeAjaxRequest('/orders/reorder-last/', 'POST', {},
                (data) => {
                    window.location.href = '{% url "menu:employee_menu" %}';
                },
                (error) => console.error('Error reordering last meal:', error)
            );
        });
    }

    // Top Up Wallet
    const processPaymentBtn = document.querySelector('.process-payment');
    if (processPaymentBtn) {
        processPaymentBtn.addEventListener('click', () => {
            const amount = document.querySelector('input[name="amount"]').value;
            const method = document.querySelector('select[name="payment_method"]').value;
            const phone = document.querySelector('input[name="phone_number"]').value;
            if (!amount || !method || !phone) {
                alert('Please fill all fields.');
                return;
            }
            makeAjaxRequest('/payments/topup/', 'POST', { amount, payment_method: method, phone_number: phone },
                (data) => {
                    alert('Top-up successful!');
                    window.location.reload();
                },
                (error) => console.error('Error processing payment:', error)
            );
        });
    }

    const cancelTopUpBtn = document.querySelector('.cancel-topup');
    if (cancelTopUpBtn) {
        cancelTopUpBtn.addEventListener('click', () => {
            document.querySelector('.topup-form').reset();
        });
    }

    // Refresh Active Orders - uses refresh_employee_orders
    const refreshOrdersBtn = document.querySelector('.refresh-orders');
    if (refreshOrdersBtn) {
        refreshOrdersBtn.addEventListener('click', (e) => {
            e.preventDefault();
            makeAjaxRequest('/orders/refresh/', 'GET', null,
                (data) => {
                    const container = document.querySelector('.active-orders-container');
                    container.innerHTML = data.orders_html;
                },
                (error) => console.error('Error refreshing orders:', error)
            );
        });
    }

    // View All Notifications
    const viewAllBtn = document.querySelector('.view-all-notifications');
    if (viewAllBtn) {
        viewAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = '/notifications/';
        });
    }

    // Place Order in no active orders
    const placeOrderBtn = document.querySelector('.place-order-no-active');
    if (placeOrderBtn) {
        placeOrderBtn.addEventListener('click', () => {
            window.location.href = '{% url "menu:employee_menu" %}';
        });
    }
});