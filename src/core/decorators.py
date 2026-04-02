from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.cache import never_cache


def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not request.user.is_superuser:
            messages.error(request, 'Acesso restrito a superusuários.')
            return redirect('chat:home')
        return view_func(request, *args, **kwargs)
    return never_cache(wrapper)
