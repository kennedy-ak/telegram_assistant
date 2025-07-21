from django.db import models
from django.utils import timezone
import uuid

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_time = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    reminder_sent = models.BooleanField(default=False)
    telegram_message_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['due_time', '-priority', 'created_at']
        
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def is_overdue(self):
        return self.due_time and self.due_time < timezone.now() and self.status == 'pending'
    
    def mark_completed(self):
        self.status = 'completed'
        self.save()

class Conversation(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    context = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Conversation {self.session_id}"

class Reminder(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')
    reminder_time = models.DateTimeField()
    message = models.TextField()
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Reminder for {self.task.title} at {self.reminder_time}"

class UserProfile(models.Model):
    user_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200, blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile for {self.name or self.user_id}"

class BotLog(models.Model):
    LOG_TYPES = [
        ('info', 'Info'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('task_created', 'Task Created'),
        ('reminder_sent', 'Reminder Sent'),
    ]
    
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    message = models.TextField()
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_log_type_display()}: {self.message[:50]}"