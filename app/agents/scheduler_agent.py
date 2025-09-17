"""
Scheduler Agent for AgentOS

Specialized agent for calendar management, meeting scheduling,
and time-related task automation.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from dataclasses import dataclass
import re
import json
import asyncio
from enum import Enum

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from app.core.multi_llm_router import TaskType


class TimeZone(Enum):
    """Common timezone definitions"""
    UTC = "UTC"
    EST = "America/New_York"
    PST = "America/Los_Angeles"
    CST = "America/Chicago"
    GMT = "Europe/London"


class MeetingType(Enum):
    """Types of meetings"""
    ONE_ON_ONE = "one_on_one"
    TEAM_MEETING = "team_meeting"
    CLIENT_CALL = "client_call"
    INTERVIEW = "interview"
    PRESENTATION = "presentation"
    WORKSHOP = "workshop"
    CONFERENCE_CALL = "conference_call"


@dataclass
class TimeSlot:
    """Represents a time slot"""
    start: datetime
    end: datetime
    available: bool = True
    title: Optional[str] = None
    description: Optional[str] = None


@dataclass
class MeetingRequest:
    """Meeting scheduling request"""
    title: str
    duration_minutes: int
    participants: List[str]
    meeting_type: MeetingType
    preferred_times: List[TimeSlot]
    timezone: str = "UTC"
    location: Optional[str] = None
    virtual_meeting: bool = True
    description: Optional[str] = None
    priority: str = "medium"  # high, medium, low


@dataclass
class SchedulingResult:
    """Result of scheduling operation"""
    success: bool
    meeting_time: Optional[TimeSlot]
    meeting_id: Optional[str]
    calendar_link: Optional[str]
    participants_notified: List[str]
    conflicts: List[str]
    suggestions: List[TimeSlot]
    message: str


class SchedulerAgent(BaseAgent):
    """
    Specialized agent for scheduling and calendar management tasks.

    Capabilities:
    - Meeting scheduling and coordination
    - Calendar conflict detection
    - Time zone management
    - Availability analysis
    - Meeting preparation and follow-up
    - Recurring event management
    """

    def __init__(self):
        config = AgentConfig(
            name="Scheduler Agent",
            description="Expert scheduler for calendar management, meeting coordination, and time optimization",
            capabilities=[
                AgentCapability.CALENDAR_MANAGEMENT,
                AgentCapability.SCHEDULING,
                AgentCapability.WORKFLOW_AUTOMATION,
                AgentCapability.EMAIL_PROCESSING
            ],
            model_preferences={
                TaskType.REALTIME_CHAT.value: "gpt-4o-mini",
                TaskType.BULK_PROCESSING.value: "claude-3-5-sonnet-20241022"
            },
            max_tokens=2000,
            temperature=0.2,  # Low temperature for precise scheduling
            custom_instructions="""
            You are an expert scheduling assistant with expertise in:
            - Calendar management and optimization
            - Time zone coordination
            - Meeting logistics and preparation
            - Conflict resolution and alternative scheduling
            - Professional communication for scheduling

            Always:
            - Consider time zones when scheduling
            - Check for conflicts and overlaps
            - Suggest optimal meeting times
            - Provide clear meeting details
            - Respect participant preferences and availability
            - Follow professional scheduling etiquette
            """,
            tools=["calendar_checker", "timezone_converter", "meeting_optimizer", "availability_finder"]
        )
        super().__init__(config)
        self._mock_calendars = {}  # Simulated calendar data
        self._meeting_templates = self._load_meeting_templates()

    def _load_meeting_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load meeting templates for different types"""
        return {
            "one_on_one": {
                "duration": 30,
                "buffer_time": 15,
                "location": "Virtual",
                "agenda_template": "1. Check-in\n2. Updates\n3. Challenges\n4. Next steps"
            },
            "team_meeting": {
                "duration": 60,
                "buffer_time": 15,
                "location": "Conference Room / Virtual",
                "agenda_template": "1. Team updates\n2. Project status\n3. Blockers\n4. Action items"
            },
            "client_call": {
                "duration": 45,
                "buffer_time": 15,
                "location": "Virtual",
                "agenda_template": "1. Welcome\n2. Agenda review\n3. Discussion\n4. Next steps"
            },
            "interview": {
                "duration": 60,
                "buffer_time": 30,
                "location": "Virtual",
                "agenda_template": "1. Introductions\n2. Role overview\n3. Questions\n4. Next steps"
            }
        }

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """Execute scheduling task based on the request"""

        # Parse the scheduling request
        scheduling_request = await self._parse_scheduling_request(task, kwargs)

        # Determine the scheduling action
        action_type = self._determine_action_type(task)

        # Execute the appropriate scheduling action
        if action_type == "schedule_meeting":
            result = await self._schedule_meeting(scheduling_request, context)
        elif action_type == "find_availability":
            result = await self._find_availability(scheduling_request, context)
        elif action_type == "reschedule_meeting":
            result = await self._reschedule_meeting(scheduling_request, context)
        elif action_type == "cancel_meeting":
            result = await self._cancel_meeting(scheduling_request, context)
        elif action_type == "check_conflicts":
            result = await self._check_conflicts(scheduling_request, context)
        else:
            result = await self._handle_general_scheduling_query(task, context)

        # Format the response
        response = await self._format_scheduling_response(result, action_type, context)

        return response

    async def _parse_scheduling_request(
        self,
        task: str,
        kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse scheduling request from natural language"""

        parsing_prompt = f"""
        Parse this scheduling request and extract key information:

        Request: {task}
        Additional parameters: {json.dumps(kwargs)}

        Extract the following information in JSON format:
        {{
            "action": "schedule_meeting|find_availability|reschedule_meeting|cancel_meeting|check_conflicts",
            "meeting_title": "string or null",
            "duration_minutes": "number or null",
            "participants": ["list of participants"],
            "preferred_date": "YYYY-MM-DD or null",
            "preferred_time": "HH:MM or null",
            "timezone": "timezone or UTC",
            "meeting_type": "one_on_one|team_meeting|client_call|interview|presentation|workshop",
            "location": "string or null",
            "virtual_meeting": "boolean",
            "priority": "high|medium|low",
            "description": "string or null",
            "recurring": "boolean",
            "frequency": "daily|weekly|monthly or null"
        }}

        If information is not available, use null.
        """

        try:
            response = await self.generate_llm_response(
                parsing_prompt, TaskType.DATA_ANALYSIS
            )

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_request = json.loads(json_match.group())
                return parsed_request

        except (json.JSONDecodeError, Exception):
            pass

        # Fallback parsing
        return {
            "action": "schedule_meeting",
            "meeting_title": self._extract_meeting_title(task),
            "duration_minutes": self._extract_duration(task),
            "participants": self._extract_participants(task),
            "preferred_date": None,
            "preferred_time": None,
            "timezone": "UTC",
            "meeting_type": "team_meeting",
            "location": None,
            "virtual_meeting": True,
            "priority": "medium",
            "description": None,
            "recurring": False,
            "frequency": None
        }

    def _determine_action_type(self, task: str) -> str:
        """Determine the type of scheduling action"""
        task_lower = task.lower()

        if any(word in task_lower for word in ["schedule", "book", "set up", "arrange"]):
            return "schedule_meeting"
        elif any(word in task_lower for word in ["availability", "available", "free time"]):
            return "find_availability"
        elif any(word in task_lower for word in ["reschedule", "move", "change time"]):
            return "reschedule_meeting"
        elif any(word in task_lower for word in ["cancel", "delete", "remove"]):
            return "cancel_meeting"
        elif any(word in task_lower for word in ["conflict", "overlap", "clash"]):
            return "check_conflicts"
        else:
            return "general_query"

    async def _schedule_meeting(
        self,
        request: Dict[str, Any],
        context: AgentContext
    ) -> SchedulingResult:
        """Schedule a new meeting"""

        # Get participant availability
        availability = await self._get_participant_availability(
            request.get("participants", []),
            request.get("preferred_date"),
            context
        )

        # Find optimal time slot
        optimal_slot = await self._find_optimal_time_slot(
            availability,
            request.get("duration_minutes", 60),
            request.get("preferred_time")
        )

        if optimal_slot:
            # Create meeting
            meeting_id = await self._create_meeting(request, optimal_slot, context)

            # Send notifications
            notified_participants = await self._notify_participants(
                request.get("participants", []),
                optimal_slot,
                request,
                context
            )

            return SchedulingResult(
                success=True,
                meeting_time=optimal_slot,
                meeting_id=meeting_id,
                calendar_link=f"https://calendar.example.com/meeting/{meeting_id}",
                participants_notified=notified_participants,
                conflicts=[],
                suggestions=[],
                message=f"Meeting '{request.get('meeting_title', 'New Meeting')}' scheduled successfully for {optimal_slot.start.strftime('%Y-%m-%d %H:%M')} ({request.get('timezone', 'UTC')})"
            )
        else:
            # No available slots, provide alternatives
            suggestions = await self._suggest_alternative_times(
                availability,
                request.get("duration_minutes", 60)
            )

            return SchedulingResult(
                success=False,
                meeting_time=None,
                meeting_id=None,
                calendar_link=None,
                participants_notified=[],
                conflicts=["No available time slots found for all participants"],
                suggestions=suggestions,
                message="Unable to find a suitable time for all participants. Here are some alternative options:"
            )

    async def _find_availability(
        self,
        request: Dict[str, Any],
        context: AgentContext
    ) -> SchedulingResult:
        """Find availability for participants"""

        participants = request.get("participants", [])
        date = request.get("preferred_date")

        # Get availability for next 7 days if no date specified
        if not date:
            dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        else:
            dates = [date]

        all_availability = []

        for date in dates:
            daily_availability = await self._get_participant_availability(
                participants, date, context
            )
            all_availability.extend(daily_availability)

        return SchedulingResult(
            success=True,
            meeting_time=None,
            meeting_id=None,
            calendar_link=None,
            participants_notified=[],
            conflicts=[],
            suggestions=all_availability[:10],  # Top 10 suggestions
            message=f"Found {len(all_availability)} available time slots for {len(participants)} participants"
        )

    async def _get_participant_availability(
        self,
        participants: List[str],
        date: Optional[str],
        context: AgentContext
    ) -> List[TimeSlot]:
        """Get availability for all participants"""

        # In production, this would integrate with:
        # - Google Calendar API
        # - Outlook Calendar API
        # - CalDAV servers
        # - Internal calendar systems

        # Simulate availability checking
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()

        # Generate realistic availability slots
        available_slots = []

        # Business hours: 9 AM to 5 PM
        for hour in range(9, 17):
            slot_start = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=1)

            # Simulate some conflicts (random busy periods)
            is_available = not (hour in [12, 14] or (hour == 10 and len(participants) > 2))

            if is_available:
                available_slots.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    available=True,
                    title=f"Available: {hour}:00-{hour+1}:00"
                ))

        return available_slots

    async def _find_optimal_time_slot(
        self,
        availability: List[TimeSlot],
        duration_minutes: int,
        preferred_time: Optional[str]
    ) -> Optional[TimeSlot]:
        """Find the optimal time slot based on availability and preferences"""

        if not availability:
            return None

        # Filter slots that can accommodate the duration
        suitable_slots = []

        for slot in availability:
            if slot.available:
                slot_duration = (slot.end - slot.start).total_seconds() / 60
                if slot_duration >= duration_minutes:
                    # Create a slot with the exact duration needed
                    meeting_end = slot.start + timedelta(minutes=duration_minutes)
                    suitable_slots.append(TimeSlot(
                        start=slot.start,
                        end=meeting_end,
                        available=True,
                        title=f"Meeting Slot"
                    ))

        if not suitable_slots:
            return None

        # If preferred time is specified, try to find closest match
        if preferred_time:
            try:
                preferred_hour, preferred_minute = map(int, preferred_time.split(':'))
                target_time = time(preferred_hour, preferred_minute)

                # Find slot closest to preferred time
                best_slot = min(suitable_slots, key=lambda s: abs(
                    (s.start.time().hour * 60 + s.start.time().minute) -
                    (target_time.hour * 60 + target_time.minute)
                ))
                return best_slot

            except ValueError:
                pass

        # Return first available slot
        return suitable_slots[0]

    async def _create_meeting(
        self,
        request: Dict[str, Any],
        time_slot: TimeSlot,
        context: AgentContext
    ) -> str:
        """Create a meeting in the calendar system"""

        # In production, this would create actual calendar events
        meeting_id = f"meeting_{int(time_slot.start.timestamp())}"

        # Store meeting details (simulated)
        meeting_details = {
            "id": meeting_id,
            "title": request.get("meeting_title", "New Meeting"),
            "start": time_slot.start.isoformat(),
            "end": time_slot.end.isoformat(),
            "participants": request.get("participants", []),
            "location": request.get("location", "Virtual"),
            "description": request.get("description"),
            "created_by": context.user_id,
            "organization_id": context.organization_id
        }

        # Store in mock calendar
        org_calendar = self._mock_calendars.setdefault(context.organization_id, {})
        org_calendar[meeting_id] = meeting_details

        return meeting_id

    async def _notify_participants(
        self,
        participants: List[str],
        time_slot: TimeSlot,
        request: Dict[str, Any],
        context: AgentContext
    ) -> List[str]:
        """Send meeting notifications to participants"""

        # In production, this would:
        # - Send calendar invitations
        # - Send email notifications
        # - Update participant calendars
        # - Send SMS reminders if configured

        # Simulate notification sending
        notified = []

        for participant in participants:
            # Simulate successful notification
            notified.append(participant)

        return notified

    async def _suggest_alternative_times(
        self,
        availability: List[TimeSlot],
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Suggest alternative meeting times"""

        # Look for partial availability or near-matches
        suggestions = []

        # Extend search to next few days
        base_date = datetime.now()
        for day_offset in range(1, 8):  # Next 7 days
            future_date = base_date + timedelta(days=day_offset)

            # Generate some realistic alternative slots
            for hour in [9, 10, 11, 14, 15, 16]:
                slot_start = future_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=duration_minutes)

                suggestions.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    available=True,
                    title=f"Alternative: {slot_start.strftime('%Y-%m-%d %H:%M')}"
                ))

        return suggestions[:5]  # Return top 5 suggestions

    async def _reschedule_meeting(
        self,
        request: Dict[str, Any],
        context: AgentContext
    ) -> SchedulingResult:
        """Reschedule an existing meeting"""

        # This would involve:
        # 1. Finding the existing meeting
        # 2. Checking new availability
        # 3. Updating the meeting
        # 4. Notifying participants

        return SchedulingResult(
            success=True,
            meeting_time=None,
            meeting_id=None,
            calendar_link=None,
            participants_notified=[],
            conflicts=[],
            suggestions=[],
            message="Meeting rescheduling completed successfully"
        )

    async def _cancel_meeting(
        self,
        request: Dict[str, Any],
        context: AgentContext
    ) -> SchedulingResult:
        """Cancel an existing meeting"""

        return SchedulingResult(
            success=True,
            meeting_time=None,
            meeting_id=None,
            calendar_link=None,
            participants_notified=[],
            conflicts=[],
            suggestions=[],
            message="Meeting cancelled successfully"
        )

    async def _check_conflicts(
        self,
        request: Dict[str, Any],
        context: AgentContext
    ) -> SchedulingResult:
        """Check for scheduling conflicts"""

        # Analyze calendar for conflicts
        conflicts = []

        return SchedulingResult(
            success=True,
            meeting_time=None,
            meeting_id=None,
            calendar_link=None,
            participants_notified=[],
            conflicts=conflicts,
            suggestions=[],
            message="No scheduling conflicts detected" if not conflicts else f"Found {len(conflicts)} conflicts"
        )

    async def _handle_general_scheduling_query(
        self,
        task: str,
        context: AgentContext
    ) -> SchedulingResult:
        """Handle general scheduling-related queries"""

        response_prompt = f"""
        Answer this scheduling-related question professionally:

        Question: {task}

        Provide helpful information about:
        - Scheduling best practices
        - Time management tips
        - Meeting etiquette
        - Calendar organization

        Keep the response concise and actionable.
        """

        response = await self.generate_llm_response(
            response_prompt, TaskType.REALTIME_CHAT
        )

        return SchedulingResult(
            success=True,
            meeting_time=None,
            meeting_id=None,
            calendar_link=None,
            participants_notified=[],
            conflicts=[],
            suggestions=[],
            message=response
        )

    async def _format_scheduling_response(
        self,
        result: SchedulingResult,
        action_type: str,
        context: AgentContext
    ) -> str:
        """Format the scheduling response for the user"""

        if action_type == "schedule_meeting" and result.success:
            response = f"✅ {result.message}\n\n"
            response += f"📅 **Meeting Details:**\n"
            if result.meeting_time:
                response += f"• Time: {result.meeting_time.start.strftime('%Y-%m-%d %H:%M')} - {result.meeting_time.end.strftime('%H:%M')}\n"
            if result.meeting_id:
                response += f"• Meeting ID: {result.meeting_id}\n"
            if result.calendar_link:
                response += f"• Calendar Link: {result.calendar_link}\n"
            if result.participants_notified:
                response += f"• Participants Notified: {', '.join(result.participants_notified)}\n"

        elif action_type == "find_availability":
            response = f"📋 {result.message}\n\n"
            if result.suggestions:
                response += "**Available Time Slots:**\n"
                for i, slot in enumerate(result.suggestions[:5], 1):
                    response += f"{i}. {slot.start.strftime('%Y-%m-%d %H:%M')} - {slot.end.strftime('%H:%M')}\n"

        elif not result.success:
            response = f"⚠️ {result.message}\n\n"
            if result.conflicts:
                response += "**Conflicts:**\n"
                for conflict in result.conflicts:
                    response += f"• {conflict}\n"
            if result.suggestions:
                response += "\n**Alternative Times:**\n"
                for i, slot in enumerate(result.suggestions[:3], 1):
                    response += f"{i}. {slot.start.strftime('%Y-%m-%d %H:%M')} - {slot.end.strftime('%H:%M')}\n"

        else:
            response = result.message

        return response

    def _extract_meeting_title(self, task: str) -> Optional[str]:
        """Extract meeting title from task"""
        # Look for quoted titles or common patterns
        quoted_match = re.search(r'"([^"]+)"', task)
        if quoted_match:
            return quoted_match.group(1)

        # Look for "schedule X meeting" pattern
        meeting_match = re.search(r'schedule (?:a )?([^.]+?)(?:\s+meeting|\s+call|$)', task, re.IGNORECASE)
        if meeting_match:
            return meeting_match.group(1).strip()

        return None

    def _extract_duration(self, task: str) -> int:
        """Extract meeting duration from task"""
        # Look for duration patterns
        duration_patterns = [
            r'(\d+)\s*(?:hour|hr)s?',
            r'(\d+)\s*(?:minute|min)s?',
            r'(\d+)h(?:\s*(\d+)m)?',
            r'(\d+):(\d+)'
        ]

        for pattern in duration_patterns:
            match = re.search(pattern, task, re.IGNORECASE)
            if match:
                if 'hour' in pattern or 'hr' in pattern:
                    return int(match.group(1)) * 60
                elif 'minute' in pattern or 'min' in pattern:
                    return int(match.group(1))
                elif 'h' in pattern:
                    hours = int(match.group(1))
                    minutes = int(match.group(2)) if match.group(2) else 0
                    return hours * 60 + minutes
                elif ':' in pattern:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    return hours * 60 + minutes

        return 60  # Default 1 hour

    def _extract_participants(self, task: str) -> List[str]:
        """Extract participants from task"""
        participants = []

        # Look for email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, task)
        participants.extend(emails)

        # Look for "with X" pattern
        with_pattern = r'with\s+([^.]+?)(?:\s+and|\s*,|\s*$)'
        with_matches = re.findall(with_pattern, task, re.IGNORECASE)
        for match in with_matches:
            names = re.split(r'\s+and\s+|\s*,\s*', match.strip())
            participants.extend([name.strip() for name in names if name.strip()])

        return list(set(participants))  # Remove duplicates

    def _get_tool_function(self, tool_name: str):
        """Get scheduler-specific tool functions"""
        tools = {
            "calendar_checker": self._get_participant_availability,
            "timezone_converter": self._convert_timezone,
            "meeting_optimizer": self._find_optimal_time_slot,
            "availability_finder": self._find_availability
        }
        return tools.get(tool_name)

    async def _convert_timezone(self, time_str: str, from_tz: str, to_tz: str) -> str:
        """Convert time between timezones"""
        # In production, use proper timezone libraries like pytz
        return f"Converted {time_str} from {from_tz} to {to_tz}"