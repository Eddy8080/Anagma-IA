from django.contrib import admin
from .models import ChatSession, ChatMessage, ChatAttachment

class ChatAttachmentInline(admin.TabularInline):
    model = ChatAttachment
    extra = 0

class ChatMessageInline(admin.StackedInline):
    model = ChatMessage
    extra = 0
    show_change_link = True
    inlines = [ChatAttachmentInline]

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'titulo', 'criado_em', 'atualizado_em']
    list_filter = ['user', 'criado_em']
    search_fields = ['titulo', 'user__username', 'user__nome_completo']
    inlines = [ChatMessageInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'timestamp']
    list_filter = ['role', 'timestamp']
    inlines = [ChatAttachmentInline]

admin.site.register(ChatAttachment)
