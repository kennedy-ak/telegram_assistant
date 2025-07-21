from django.contrib import admin
from .models import Task, Conversation, Reminder, BotLog

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'due_time', 'created_at']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_editable = ['status', 'priority']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'status', 'priority')
        }),
        ('Timing', {
            'fields': ('due_time', 'reminder_sent')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'telegram_message_id'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    search_fields = ['session_id']

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ['task', 'reminder_time', 'is_sent', 'created_at']
    list_filter = ['is_sent', 'reminder_time']
    readonly_fields = ['created_at']

@admin.register(BotLog)
class BotLogAdmin(admin.ModelAdmin):
    list_display = ['log_type', 'message', 'created_at']
    list_filter = ['log_type', 'created_at']
    readonly_fields = ['created_at']
    search_fields = ['message']