from openai import OpenAI
from django.conf import settings
from typing import Dict, List, Optional
import json
import re
from datetime import datetime, timedelta
import pytz

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def get_assistant_response(self, message: str, context: Dict = None, user_profile=None) -> str:
        """Get a natural response from OpenAI GPT with conversation context"""
        # Build personalized system prompt
        base_prompt = """You are a friendly, proactive AI productivity assistant integrated with a Telegram bot. 
        Your role is to:
        - Have natural conversations with the user
        - Help manage tasks and reminders  
        - Provide productivity tips and motivation
        - Answer general questions helpfully
        - Be encouraging and supportive
        - Remember previous conversations and maintain context
        
        Keep responses concise but warm. Use emojis occasionally to feel more human.
        If the user mentions tasks, deadlines, or reminders, acknowledge them naturally.
        Reference previous parts of the conversation when relevant."""
        
        # Add personalization if profile exists
        if user_profile and (user_profile.name or user_profile.occupation):
            personal_info = f"\n\nPersonal Context:\n"
            if user_profile.name:
                personal_info += f"- User's name: {user_profile.name}\n"
            if user_profile.occupation:
                personal_info += f"- User's occupation: {user_profile.occupation}\n"
            personal_info += "Use this information to provide personalized, relevant assistance. Address them by name when appropriate and tailor suggestions to their profession."
            system_prompt = base_prompt + personal_info
        else:
            system_prompt = base_prompt
        
        try:
            # Build messages with conversation context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if available
            if context and "messages" in context:
                # Add last few exchanges for context (limit to avoid token limits)
                recent_messages = context["messages"][-10:]  # Last 5 exchanges
                messages.extend(recent_messages)
            
            # Add current user message
            messages.append({"role": "user", "content": message})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Sorry, I'm having trouble thinking right now. Could you try again? 🤔"
    
    def parse_task_from_message(self, message: str) -> Optional[Dict]:
        """Extract task information from natural language"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        
        system_prompt = f"""
        You are a task parser. Extract task information from natural language input.
        
        IMPORTANT: Today's date is {current_date} and current time is {current_time}.
        Use this as reference for relative dates like "today", "tomorrow", "next week", etc.
        
        Return ONLY a JSON object with these fields:
        - title: string (required)
        - description: string (optional)
        - due_time: ISO datetime string (optional, if time mentioned) - USE CORRECT DATES BASED ON TODAY'S DATE
        - priority: "low"|"medium"|"high"|"urgent" (default: "medium")
        
        Priority Detection Rules:
        - "urgent", "ASAP", "immediately", "critical" = "urgent"
        - "high priority", "important", "high", "must do" = "high"  
        - "low priority", "low", "when I can", "not urgent" = "low"
        - Default = "medium"
        
        If no clear task is mentioned, return null.
        
        Examples for {current_date}:
        "Remind me to call mom at 6 PM today" -> {{"title": "Call mom", "due_time": "{current_date}T18:00:00Z", "priority": "medium"}}
        "URGENT: Submit assignment tomorrow at 9 AM" -> {{"title": "Submit assignment", "due_time": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}T09:00:00Z", "priority": "urgent"}}
        "High priority: Call client today" -> {{"title": "Call client", "due_time": "{current_date}T12:00:00Z", "priority": "high"}}
        "Buy groceries when I can" -> {{"title": "Buy groceries", "priority": "low"}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            if result.lower() == 'null':
                return None
            
            return json.loads(result)
        except Exception as e:
            print(f"Error parsing task: {e}")
            return None
    
    def suggest_daily_schedule(self, tasks: List[str], available_hours: str = "9 AM to 6 PM") -> str:
        """Generate a suggested daily schedule"""
        tasks_text = "\n".join([f"- {task}" for task in tasks])
        
        prompt = f"""
        Create a productive daily schedule for these tasks:
        {tasks_text}
        
        Available time: {available_hours}
        Include breaks and be realistic about time allocation.
        Format as a simple, motivating schedule with times.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return "I'll help you organize these tasks throughout your day! 📅"
    
    def get_motivational_message(self) -> str:
        """Get a random motivational message"""
        prompts = [
            "Give me a short, encouraging productivity tip for the day.",
            "Share a brief motivational quote about achieving goals.",
            "Provide an uplifting message about staying organized and productive.",
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompts[datetime.now().day % len(prompts)]}],
                max_tokens=100,
                temperature=0.8
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return "You've got this! Every small step counts towards your goals. 🌟"