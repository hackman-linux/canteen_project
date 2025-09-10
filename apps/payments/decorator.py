from functools import wraps
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout

def payment_reauth_required(view_func):
    """
    Decorator that forces re-authentication before running a payment view.
    The user must POST 'username' and 'password' in the request.
    After the view executes, the session is flushed (logout).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.method != "POST":
            return JsonResponse({"error": "Re-authentication required (POST only)"}, status=405)

        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            return JsonResponse({"error": "Username and password required"}, status=400)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse({"error": "Invalid credentials"}, status=403)

        # Temporarily log in
        login(request, user)

        # Run the payment view
        response = view_func(request, *args, **kwargs)

        # Force logout immediately after processing
        logout(request)

        return response

    return _wrapped_view
