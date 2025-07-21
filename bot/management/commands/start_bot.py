from django.core.management.base import BaseCommand
from bot.telegram_bot import telegram_bot
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start the Telegram bot'
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Telegram Assistant Bot...')
        )
        
        try:
            telegram_bot.run()
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('Bot stopped by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Bot error: {e}')
            )

# ## 10. tasks.py (Celery tasks - Alternative to APScheduler)
# ```python
# from celery import Celery
# from django.conf import settings
# from django.utils import timezone
# from datetime import timedelta
# import asyncio
# import logging

# # Initialize Celery
# app = Celery('telegram_assistant')
# app.config_from_object('django.conf:settings', namespace='CELERY')

# logger = logging.getLogger(__name__)

# @app.task
# def send_task_reminder(task_id):
#     """Celery task to send reminder"""
#     from bot.telegram_bot import telegram_bot
#     asyncio.run(telegram_bot.send_reminder(task_id))

# @app.task
# def send_daily_greeting():
#     """Celery task for daily greeting"""
#     from bot.telegram_bot import telegram_bot
#     asyncio.run(telegram_bot.send_daily_greeting())

# @app.task
# def check_overdue_tasks():
#     """Check for overdue tasks"""
#     from bot.models import Task
    
#     now = timezone.now()
#     overdue_tasks = Task.objects.filter(
#         due_time__lt=now,
#         status='pending'
#     )
    
#     count = overdue_tasks.update(status='overdue')
#     if count > 0:
#         logger.info(f"Marked {count} tasks as overdue")

# # Schedule recurring tasks
# from celery.schedules import crontab

# app.conf.beat_schedule = {
#     'daily-greeting': {
#         'task': 'tasks.send_daily_greeting',
#         'schedule': crontab(hour=8, minute=0),  # 8:00 AM daily
#     },
#     'check-overdue': {
#         'task': 'tasks.check_overdue_tasks',
#         'schedule': crontab(minute=0),  # Every hour
#     },
# }

# app.conf.timezone = settings.TIME_ZONE
