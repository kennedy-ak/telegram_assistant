import logging
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Task, Conversation, BotLog, UserProfile
from .openai_service import OpenAIService
from .scheduler import schedule_reminder
import asyncio
from asgiref.sync import sync_to_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self.openai_service = OpenAIService()
        self.setup_handlers()
        
    def setup_handlers(self):
        """Setup all bot command and message handlers"""
        # Commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("today", self.today_command))
        self.application.add_handler(CommandHandler("week", self.week_command))
        self.application.add_handler(CommandHandler("add", self.add_task_command))
        self.application.add_handler(CommandHandler("complete", self.complete_task_command))
        self.application.add_handler(CommandHandler("schedule", self.schedule_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        
        # Callback queries (for inline buttons)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Text messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def setup_bot_commands(self):
        """Set up bot command menu"""
        from telegram import BotCommand
        commands = [
            BotCommand("start", "🚀 Get started with the bot"),
            BotCommand("today", "📅 View today's tasks"),
            BotCommand("week", "📋 View this week's tasks"),
            BotCommand("add", "➕ Add a new task"),
            BotCommand("complete", "✅ Mark tasks as complete"),
            BotCommand("schedule", "🗓️ Get schedule suggestions"),
            BotCommand("profile", "👤 Set up your profile"),
            BotCommand("help", "❓ Show help menu")
        ]
        
        await self.application.bot.set_my_commands(commands)
    
    def is_authorized(self, update: Update) -> bool:
        """Check if user is authorized"""
        try:
            authorized_id = int(settings.AUTHORIZED_USER_ID) if settings.AUTHORIZED_USER_ID else None
            return update.effective_user.id == authorized_id
        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not self.is_authorized(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        # Set up bot commands when user starts
        await self.setup_bot_commands()
            
        welcome_message = """
🤖 **Welcome to your Personal Assistant!**

I'm here to help you stay organized and productive. Here's what I can do:

📝 **Task Management:**
• Add tasks naturally: "Remind me to call John at 3 PM"
• View today's tasks: `/today`
• View this week: `/week`
• Complete tasks: `/complete`

💬 **Natural Conversation:**
• Ask me anything!
• Get productivity tips
• I'll help you stay motivated

⏰ **Smart Reminders:**
• I'll remind you 15 minutes before each task
• Daily morning check-ins at 8 AM

🗓️ **Scheduling:**
• Get schedule suggestions: `/schedule`
• I'll help organize your day

Just start chatting with me naturally! 😊
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        
        # Log the interaction
        await sync_to_async(BotLog.objects.create)(
            log_type='info',
            message=f'User started bot: {update.effective_user.username}'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_authorized(update):
            return
            
        help_text = """
🆘 **Available Commands:**

`/start` - Get started
`/today` - View today's tasks
`/week` - View this week's tasks  
`/add <task>` - Add a new task
`/complete` - Mark tasks as complete
`/schedule` - Get daily schedule suggestions
`/help` - Show this help

💡 **Natural Language Examples:**
• "Remind me to submit report tomorrow at 2 PM"
• "I need to buy groceries today"
• "Schedule a meeting with Sarah next week"
• "What should I focus on today?"

Just chat with me naturally! 🗣️
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's tasks"""
        if not self.is_authorized(update):
            return
            
        today = timezone.now().date()
        tasks = await sync_to_async(list)(Task.objects.filter(
            due_time__date=today,
            status='pending'
        ).order_by('due_time'))
        
        if not tasks:
            message = "📅 **Today's Schedule**\n\nNo tasks scheduled for today! Enjoy your free time or add some tasks. 😊"
        else:
            message = "📅 **Today's Schedule**\n\n"
            for i, task in enumerate(tasks, 1):
                time_str = task.due_time.strftime("%H:%M") if task.due_time else "No time set"
                priority_emoji = self.get_priority_emoji(task.priority)
                message += f"{i}. {priority_emoji} **{task.title}** - {time_str}\n"
                if task.description:
                    message += f"   ↳ {task.description}\n"
                message += "\n"
        
        # Add inline keyboard for task management
        keyboard = [
            [InlineKeyboardButton("✅ Complete Task", callback_data="complete_task")],
            [InlineKeyboardButton("➕ Add New Task", callback_data="add_task")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def week_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show this week's tasks"""
        if not self.is_authorized(update):
            return
            
        today = timezone.now().date()
        week_end = today + timedelta(days=7)
        
        tasks = await sync_to_async(list)(Task.objects.filter(
            due_time__date__range=[today, week_end],
            status='pending'
        ).order_by('due_time'))
        
        if not tasks:
            message = "📋 **This Week's Tasks**\n\nNo tasks scheduled for this week!"
        else:
            message = "📋 **This Week's Tasks**\n\n"
            current_date = None
            
            for task in tasks:
                task_date = task.due_time.date() if task.due_time else today
                
                if task_date != current_date:
                    current_date = task_date
                    day_name = task_date.strftime("%A, %B %d")
                    message += f"**{day_name}**\n"
                
                time_str = task.due_time.strftime("%H:%M") if task.due_time else "No time"
                priority_emoji = self.get_priority_emoji(task.priority)
                message += f"  {priority_emoji} {task.title} - {time_str}\n"
                
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def add_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command"""
        if not self.is_authorized(update):
            return
            
        if not context.args:
            await update.message.reply_text("Please specify a task. Example: `/add Call mom at 6 PM`", parse_mode='Markdown')
            return
        
        task_text = " ".join(context.args)
        await self.create_task_from_text(update, task_text)
    
    async def complete_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show tasks to complete"""
        if not self.is_authorized(update):
            return
            
        tasks = await sync_to_async(list)(Task.objects.filter(status='pending').order_by('due_time')[:10])
        
        if not tasks:
            await update.message.reply_text("🎉 No pending tasks! You're all caught up!")
            return
        
        message = "✅ **Select a task to complete:**\n\n"
        keyboard = []
        
        for i, task in enumerate(tasks, 1):
            time_str = task.due_time.strftime("%m/%d %H:%M") if task.due_time else "No time"
            message += f"{i}. {task.title} - {time_str}\n"
            keyboard.append([InlineKeyboardButton(f"✅ {task.title[:30]}...", 
                                                callback_data=f"complete_{task.id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate schedule suggestions"""
        if not self.is_authorized(update):
            return
            
        today = timezone.now().date()
        tasks = await sync_to_async(list)(Task.objects.filter(
            due_time__date=today,
            status='pending'
        ).values_list('title', flat=True))
        
        if not tasks:
            await update.message.reply_text("No tasks for today. How about planning tomorrow? 📅")
            return
        
        schedule = self.openai_service.suggest_daily_schedule(tasks)
        
        message = f"🗓️ **Suggested Schedule for Today:**\n\n{schedule}"
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command"""
        if not self.is_authorized(update):
            return
        
        user_id = str(update.effective_user.id)
        
        if not context.args:
            # Show current profile
            profile = await self.get_user_profile(user_id)
            if profile.name or profile.occupation:
                message = f"👤 **Your Profile:**\n\n"
                if profile.name:
                    message += f"**Name:** {profile.name}\n"
                if profile.occupation:
                    message += f"**Occupation:** {profile.occupation}\n"
                message += f"\nTo update: `/profile name [Your Name] occupation [Your Job]`"
            else:
                message = "👤 **Set up your profile for a personal touch!**\n\n"
                message += "Usage: `/profile name Kennedy occupation Software Developer`\n\n"
                message += "This helps me provide more personalized assistance! 😊"
        else:
            # Parse and update profile
            args_text = " ".join(context.args)
            name = None
            occupation = None
            
            if "name " in args_text:
                name_part = args_text.split("name ")[1]
                if " occupation " in name_part:
                    name = name_part.split(" occupation ")[0].strip()
                    occupation = name_part.split(" occupation ")[1].strip()
                else:
                    name = name_part.strip()
            elif "occupation " in args_text:
                occupation = args_text.split("occupation ")[1].strip()
            
            if name or occupation:
                await self.update_user_profile(user_id, name, occupation)
                message = f"✅ **Profile Updated!**\n\n"
                if name:
                    message += f"**Name:** {name}\n"
                if occupation:
                    message += f"**Occupation:** {occupation}\n"
                message += "\nNow I can provide more personalized assistance! 🎉"
            else:
                message = "❌ Please use the format: `/profile name [Your Name] occupation [Your Job]`"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages"""
        if not self.is_authorized(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        user_message = update.message.text
        user_id = str(update.effective_user.id)
        
        # Get user profile and conversation context
        user_profile = await self.get_user_profile(user_id)
        conversation_context = await self.get_conversation_context(user_id)
        
        # First, try to parse as a task
        task_data = self.openai_service.parse_task_from_message(user_message)
        
        if task_data:
            await self.create_task_from_parsed_data(update, task_data, user_message)
        else:
            # Get conversational response with context and profile
            try:
                response = self.openai_service.get_assistant_response(
                    user_message, 
                    conversation_context, 
                    user_profile
                )
                await update.message.reply_text(response)
                
                # Update conversation context
                await self.update_conversation_context(user_id, user_message, response)
                
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await update.message.reply_text("Sorry, I'm having trouble right now. Please try again! 🤔")
        
        # Log the conversation
        await sync_to_async(BotLog.objects.create)(
            log_type='info',
            message=f'Conversation: {user_message[:100]}',
            extra_data={'response_type': 'task' if task_data else 'conversation'}
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("complete_"):
            task_id = query.data.split("_", 1)[1]
            try:
                task = await sync_to_async(Task.objects.get)(id=task_id)
                await sync_to_async(task.mark_completed)()
                
                # Stop recurring reminders for high/urgent priority tasks
                if task.priority in ['high', 'urgent']:
                    try:
                        from .scheduler import stop_recurring_reminders
                        stop_recurring_reminders(task_id)
                    except Exception as e:
                        logger.error(f"Error stopping reminders for completed task: {e}")
                
                await query.edit_message_text(f"✅ Completed: **{task.title}**\n\nGreat job! 🎉", parse_mode='Markdown')
                
                await sync_to_async(BotLog.objects.create)(
                    log_type='task_completed',
                    message=f'Task completed: {task.title}',
                    extra_data={'task_id': str(task.id)}
                )
            except Task.DoesNotExist:
                await query.edit_message_text("❌ Task not found.")
        
        elif query.data.startswith("stop_reminders_"):
            task_id = query.data.split("_", 2)[2]
            try:
                from .scheduler import stop_recurring_reminders
                stop_recurring_reminders(task_id)
                
                task = await sync_to_async(Task.objects.get)(id=task_id)
                await query.edit_message_text(f"🔕 **Reminders Stopped**\n\nNo more recurring reminders for: **{task.title}**\n\nYou can still complete it using `/complete` command.", parse_mode='Markdown')
                
                await sync_to_async(BotLog.objects.create)(
                    log_type='info',
                    message=f'Recurring reminders stopped for task: {task.title}',
                    extra_data={'task_id': str(task.id)}
                )
            except Task.DoesNotExist:
                await query.edit_message_text("❌ Task not found.")
            except Exception as e:
                logger.error(f"Error stopping reminders: {e}")
                await query.edit_message_text("❌ Error stopping reminders.")
        
        elif query.data == "add_task":
            await query.edit_message_text("📝 Just tell me what you need to do! For example:\n\n• \"Remind me to call John at 3 PM\"\n• \"HIGH PRIORITY: Submit report by Friday\"\n• \"URGENT: Buy groceries today\"")
        
        elif query.data == "complete_task":
            await self.complete_task_command(update, context)
    
    async def create_task_from_text(self, update: Update, task_text: str):
        """Create task from plain text"""
        task_data = self.openai_service.parse_task_from_message(task_text)
        
        if task_data:
            await self.create_task_from_parsed_data(update, task_data, task_text)
        else:
            # Fallback: create simple task
            task = await sync_to_async(Task.objects.create)(
                title=task_text[:200],
                description="",
                priority='medium'
            )
            
            await update.message.reply_text(f"📝 Added task: **{task.title}**")
    
    async def create_task_from_parsed_data(self, update: Update, task_data: Dict, original_message: str):
        """Create task from parsed OpenAI data"""
        try:
            # Parse due time if provided
            due_time = None
            if task_data.get('due_time'):
                try:
                    # Parse the datetime and make it timezone aware
                    due_time = datetime.fromisoformat(task_data['due_time'].replace('Z', '+00:00'))
                    # Convert to current timezone if needed
                    if due_time.tzinfo is None:
                        due_time = timezone.make_aware(due_time)
                except Exception as e:
                    logger.error(f"Error parsing due_time: {e}")
                    due_time = None
            
            task = await sync_to_async(Task.objects.create)(
                title=task_data['title'],
                description=task_data.get('description', ''),
                due_time=due_time,
                priority=task_data.get('priority', 'medium'),
                telegram_message_id=update.message.message_id
            )
            
            # Schedule reminder if due time is set
            if task.due_time:
                await sync_to_async(schedule_reminder)(task)
            
            # Prepare response message
            response = f"✅ **Task Added:**\n\n📝 {task.title}"
            if task.description:
                response += f"\n💭 {task.description}"
            if task.due_time:
                response += f"\n⏰ Due: {task.due_time.strftime('%B %d, %Y at %I:%M %p')}"
            response += f"\n🔥 Priority: {task.get_priority_display()}"
            
            # Add motivational message
            if task.due_time and task.due_time.date() == timezone.now().date():
                response += "\n\n💪 You've got this! I'll remind you before it's due."
            
            await update.message.reply_text(response, parse_mode='Markdown')
            
            # Log task creation
            await sync_to_async(BotLog.objects.create)(
                log_type='task_created',
                message=f'Task created: {task.title}',
                extra_data={'task_id': str(task.id), 'original_message': original_message}
            )
            
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't create that task. Could you try rephrasing it?")
    
    def get_priority_emoji(self, priority: str) -> str:
        """Get emoji for task priority"""
        emoji_map = {
            'low': '🟢',
            'medium': '🟡', 
            'high': '🟠',
            'urgent': '🔴'
        }
        return emoji_map.get(priority, '🟡')
    
    async def get_conversation_context(self, user_id: str) -> Dict:
        """Get or create conversation context for user"""
        try:
            conversation = await sync_to_async(Conversation.objects.get)(session_id=user_id)
            return conversation.context
        except Conversation.DoesNotExist:
            # Create new conversation
            conversation = await sync_to_async(Conversation.objects.create)(
                session_id=user_id,
                context={"messages": []}
            )
            return conversation.context
    
    async def update_conversation_context(self, user_id: str, user_message: str, bot_response: str):
        """Update conversation context with new messages"""
        try:
            conversation = await sync_to_async(Conversation.objects.get)(session_id=user_id)
            
            # Add new messages to context (keep last 10 exchanges)
            messages = conversation.context.get("messages", [])
            messages.append({"role": "user", "content": user_message})
            messages.append({"role": "assistant", "content": bot_response})
            
            # Keep only last 20 messages (10 exchanges)
            if len(messages) > 20:
                messages = messages[-20:]
            
            conversation.context["messages"] = messages
            await sync_to_async(conversation.save)()
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {e}")
    
    async def get_user_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile"""
        try:
            profile = await sync_to_async(UserProfile.objects.get)(user_id=user_id)
            return profile
        except UserProfile.DoesNotExist:
            profile = await sync_to_async(UserProfile.objects.create)(user_id=user_id)
            return profile
    
    async def update_user_profile(self, user_id: str, name: str = None, occupation: str = None):
        """Update user profile information"""
        try:
            profile = await self.get_user_profile(user_id)
            if name:
                profile.name = name
            if occupation:
                profile.occupation = occupation
            await sync_to_async(profile.save)()
            return profile
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return None
    
    async def send_daily_greeting(self):
        """Send daily morning greeting"""
        try:
            motivational_message = self.openai_service.get_motivational_message()
            
            today = timezone.now().date()
            tasks_count = await sync_to_async(Task.objects.filter(
                due_time__date=today,
                status='pending'
            ).count)()
            
            greeting = f"🌅 **Good morning!** {motivational_message}\n\n"
            
            if tasks_count > 0:
                greeting += f"📋 You have {tasks_count} task{'s' if tasks_count != 1 else ''} scheduled for today. "
                greeting += "Type `/today` to see them or just tell me what else you'd like to add! 😊"
            else:
                greeting += "🆓 Your schedule is clear today! What would you like to accomplish? Just tell me your plans and I'll help you stay organized."
            
            await self.application.bot.send_message(
                chat_id=settings.AUTHORIZED_USER_ID,
                text=greeting,
                parse_mode='Markdown'
            )
            
            await sync_to_async(BotLog.objects.create)(
                log_type='info',
                message='Daily greeting sent',
                extra_data={'tasks_count': tasks_count}
            )
            
        except Exception as e:
            logger.error(f"Error sending daily greeting: {e}")
    
    async def send_reminder(self, task_id: str, custom_message: str = None, reminder_type: str = "standard"):
        """Send task reminder"""
        try:
            task = await sync_to_async(Task.objects.get)(id=task_id)
            
            # Skip if task is already completed
            if task.status == 'completed':
                return
            
            if custom_message:
                message = custom_message
            else:
                time_left = task.due_time - timezone.now()
                minutes_left = int(time_left.total_seconds() / 60)
                
                priority_emoji = self.get_priority_emoji(task.priority)
                
                if "urgent" in reminder_type:
                    message = f"🚨 **URGENT REMINDER!** {priority_emoji}\n\n"
                elif "high" in reminder_type:
                    message = f"🔔 **HIGH PRIORITY REMINDER!** {priority_emoji}\n\n"
                else:
                    message = f"⏰ **Reminder!** {priority_emoji}\n\n"
                
                message += f"📝 {task.title}\n"
                if task.description:
                    message += f"💭 {task.description}\n"
                
                if minutes_left > 0:
                    message += f"⏱️ Due in {minutes_left} minutes!\n\n"
                elif minutes_left < 0:
                    message += f"⚠️ Overdue by {abs(minutes_left)} minutes!\n\n"
                else:
                    message += f"⏱️ Due NOW!\n\n"
                
                message += "Good luck! You've got this! 💪"
            
            # Add buttons based on priority
            keyboard = []
            keyboard.append([InlineKeyboardButton("✅ Mark Complete", callback_data=f"complete_{task.id}")])
            
            # Add stop reminders button for high/urgent priority
            if task.priority in ['high', 'urgent']:
                keyboard.append([InlineKeyboardButton("🔕 Stop Reminders", callback_data=f"stop_reminders_{task.id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.application.bot.send_message(
                chat_id=settings.AUTHORIZED_USER_ID,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            await sync_to_async(BotLog.objects.create)(
                log_type='reminder_sent',
                message=f'Reminder sent for task: {task.title} ({reminder_type})',
                extra_data={'task_id': str(task.id), 'reminder_type': reminder_type}
            )
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found for reminder")
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
    
    async def send_recurring_reminder(self, task_id: str):
        """Send recurring reminder for high/urgent priority tasks"""
        try:
            task = await sync_to_async(Task.objects.get)(id=task_id)
            
            # Stop recurring if task is completed
            if task.status == 'completed':
                from .scheduler import stop_recurring_reminders
                stop_recurring_reminders(task_id)
                return
            
            time_overdue = timezone.now() - task.due_time
            minutes_overdue = int(time_overdue.total_seconds() / 60)
            
            priority_emoji = self.get_priority_emoji(task.priority)
            
            if task.priority == 'urgent':
                message = f"🚨 **URGENT - STILL PENDING!** {priority_emoji}\n\n"
            else:
                message = f"🔔 **HIGH PRIORITY - STILL PENDING!** {priority_emoji}\n\n"
            
            message += f"📝 {task.title}\n"
            if task.description:
                message += f"💭 {task.description}\n"
            message += f"⚠️ Overdue by {minutes_overdue} minutes!\n\n"
            message += "Please complete this important task! 🎯"
            
            # Add buttons
            keyboard = [
                [InlineKeyboardButton("✅ Mark Complete", callback_data=f"complete_{task.id}")],
                [InlineKeyboardButton("🔕 Stop Reminders", callback_data=f"stop_reminders_{task.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.application.bot.send_message(
                chat_id=settings.AUTHORIZED_USER_ID,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Task.DoesNotExist:
            from .scheduler import stop_recurring_reminders
            stop_recurring_reminders(task_id)
        except Exception as e:
            logger.error(f"Error sending recurring reminder: {e}")
    
    def run(self):
        """Run the bot"""
        logger.info("Starting Telegram bot...")
        self.application.run_polling()

# Global bot instance
telegram_bot = TelegramBot()
