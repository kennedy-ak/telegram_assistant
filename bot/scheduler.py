from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from django.utils import timezone
from datetime import timedelta
import logging
import asyncio
from .models import Task, Reminder
from django.conf import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()
scheduler.start()

def schedule_reminder(task):
    """Schedule reminders for a task based on priority"""
    if not task.due_time:
        return
    
    # Different reminder timing based on priority
    if task.priority == 'urgent':
        # Urgent: 30 min, 15 min, 5 min before, then every 5 min after due time
        reminder_times = [30, 15, 5]
        for minutes in reminder_times:
            reminder_time = task.due_time - timedelta(minutes=minutes)
            if reminder_time > timezone.now():
                schedule_single_reminder(task, reminder_time, f"urgent_{minutes}min")
        
        # Schedule recurring reminders after due time for urgent tasks
        schedule_recurring_reminder(task)
        
    elif task.priority == 'high':
        # High: 15 min before, then every 5 min after due time until completed
        reminder_time = task.due_time - timedelta(minutes=15)
        if reminder_time > timezone.now():
            schedule_single_reminder(task, reminder_time, "high_15min")
        
        # Schedule recurring reminders after due time for high priority
        schedule_recurring_reminder(task)
        
    else:
        # Medium/Low: 15 minutes before due time only
        reminder_time = task.due_time - timedelta(minutes=15)
        if reminder_time > timezone.now():
            schedule_single_reminder(task, reminder_time, "standard_15min")

def schedule_single_reminder(task, reminder_time, reminder_type):
    """Schedule a single reminder"""
    try:
        reminder = Reminder.objects.create(
            task=task,
            reminder_time=reminder_time,
            message=f"Reminder for: {task.title}"
        )
        
        job_id = f"reminder_{task.id}_{reminder_type}"
        
        scheduler.add_job(
            send_reminder_job,
            trigger=DateTrigger(run_date=reminder_time),
            args=[str(task.id), reminder_type],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled {reminder_type} reminder for task {task.title} at {reminder_time}")
    except Exception as e:
        logger.error(f"Error scheduling reminder: {e}")

def schedule_recurring_reminder(task):
    """Schedule recurring reminders for high/urgent priority tasks after due time"""
    try:
        # Start recurring reminders 5 minutes after due time
        start_time = task.due_time + timedelta(minutes=5)
        
        if start_time > timezone.now():
            job_id = f"recurring_{task.id}"
            
            scheduler.add_job(
                send_recurring_reminder_job,
                'interval',
                minutes=5,  # Every 5 minutes
                start_date=start_time,
                args=[str(task.id)],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled recurring reminders for task {task.title} starting at {start_time}")
    except Exception as e:
        logger.error(f"Error scheduling recurring reminder: {e}")

def stop_recurring_reminders(task_id):
    """Stop recurring reminders for a task"""
    try:
        job_id = f"recurring_{task_id}"
        scheduler.remove_job(job_id)
        logger.info(f"Stopped recurring reminders for task {task_id}")
    except Exception as e:
        logger.error(f"Error stopping recurring reminders: {e}")

def send_reminder_job(task_id: str, reminder_type: str = "standard"):
    """Job function to send reminder (sync wrapper for async)"""
    asyncio.run(send_reminder_async(task_id, reminder_type))

async def send_reminder_async(task_id: str, reminder_type: str = "standard"):
    """Async function to send reminder"""
    from .telegram_bot import telegram_bot
    await telegram_bot.send_reminder(task_id, reminder_type=reminder_type)

def send_recurring_reminder_job(task_id: str):
    """Job function to send recurring reminder"""
    asyncio.run(send_recurring_reminder_async(task_id))

async def send_recurring_reminder_async(task_id: str):
    """Async function to send recurring reminder"""
    from .telegram_bot import telegram_bot
    await telegram_bot.send_recurring_reminder(task_id)

def schedule_daily_greeting():
    """Schedule daily greeting at 8:00 AM"""
    scheduler.add_job(
        send_daily_greeting_job,
        'cron',
        hour=8,
        minute=0,
        id='daily_greeting',
        replace_existing=True
    )
    logger.info("Scheduled daily greeting at 8:00 AM")

def send_daily_greeting_job():
    """Job function to send daily greeting"""
    asyncio.run(send_daily_greeting_async())

async def send_daily_greeting_async():
    """Async function to send daily greeting"""
    from .telegram_bot import telegram_bot
    await telegram_bot.send_daily_greeting()

def check_overdue_tasks():
    """Check and update overdue tasks"""
    now = timezone.now()
    overdue_tasks = Task.objects.filter(
        due_time__lt=now,
        status='pending'
    )
    
    for task in overdue_tasks:
        task.status = 'overdue'
        task.save()
    
    if overdue_tasks.exists():
        logger.info(f"Marked {overdue_tasks.count()} tasks as overdue")

# Schedule recurring jobs
scheduler.add_job(
    check_overdue_tasks,
    'interval',
    hours=1,
    id='check_overdue',
    replace_existing=True
)

# Initialize daily greeting schedule
schedule_daily_greeting()