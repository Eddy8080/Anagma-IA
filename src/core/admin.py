from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, GlobalIdeia

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'nome_completo', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('nome_completo',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('nome_completo',)}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(GlobalIdeia)
