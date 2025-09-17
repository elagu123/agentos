"""
Email Responder Agent for AgentOS

Specialized agent for email processing, automated responses,
and email communication management.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import json
import asyncio
from datetime import datetime, timedelta

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from app.core.multi_llm_router import TaskType


class EmailPriority(Enum):
    """Email priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class EmailType(Enum):
    """Types of emails"""
    CUSTOMER_INQUIRY = "customer_inquiry"
    SUPPORT_REQUEST = "support_request"
    SALES_LEAD = "sales_lead"
    INTERNAL_COMMUNICATION = "internal_communication"
    VENDOR_COMMUNICATION = "vendor_communication"
    MARKETING_RESPONSE = "marketing_response"
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    SPAM = "spam"
    GENERAL = "general"


class ResponseAction(Enum):
    """Possible response actions"""
    AUTO_REPLY = "auto_reply"
    DRAFT_RESPONSE = "draft_response"
    FORWARD_TO_HUMAN = "forward_to_human"
    ESCALATE = "escalate"
    CATEGORIZE_ONLY = "categorize_only"
    IGNORE = "ignore"


@dataclass
class EmailData:
    """Email data structure"""
    subject: str
    sender: str
    recipients: List[str]
    body: str
    timestamp: datetime
    thread_id: Optional[str] = None
    attachments: List[str] = None
    html_body: Optional[str] = None
    headers: Dict[str, str] = None


@dataclass
class EmailAnalysis:
    """Email analysis result"""
    email_type: EmailType
    priority: EmailPriority
    sentiment: str  # positive, neutral, negative
    intent: str
    key_topics: List[str]
    action_required: bool
    urgency_indicators: List[str]
    business_impact: str  # high, medium, low
    confidence_score: float


@dataclass
class EmailResponse:
    """Email response data"""
    action: ResponseAction
    draft_subject: Optional[str]
    draft_body: Optional[str]
    recipient: str
    cc_recipients: List[str]
    suggested_tone: str
    escalation_reason: Optional[str]
    follow_up_required: bool
    follow_up_date: Optional[datetime]
    internal_notes: Optional[str]


class EmailResponderAgent(BaseAgent):
    """
    Specialized agent for email processing and automated responses.

    Capabilities:
    - Email classification and prioritization
    - Automated response generation
    - Sentiment analysis
    - Intent recognition
    - Escalation management
    - Email routing and delegation
    """

    def __init__(self):
        config = AgentConfig(
            name="Email Responder Agent",
            description="Expert email processor for automated responses, classification, and communication management",
            capabilities=[
                AgentCapability.EMAIL_PROCESSING,
                AgentCapability.TEXT_GENERATION,
                AgentCapability.SENTIMENT_ANALYSIS,
                AgentCapability.WORKFLOW_AUTOMATION
            ],
            model_preferences={
                TaskType.REALTIME_CHAT.value: "claude-3-5-sonnet-20241022",
                TaskType.BULK_PROCESSING.value: "gpt-4o",
                TaskType.DATA_ANALYSIS.value: "gpt-4o-mini"
            },
            max_tokens=2500,
            temperature=0.4,  # Balanced for professional yet personalized responses
            custom_instructions="""
            You are an expert email processing assistant with expertise in:
            - Professional email communication
            - Customer service best practices
            - Email classification and prioritization
            - Sentiment analysis and intent recognition
            - Escalation management
            - Business communication etiquette

            Always:
            - Maintain professional and helpful tone
            - Understand the context and intent behind emails
            - Provide accurate classifications and priorities
            - Generate appropriate responses based on business context
            - Recognize when human intervention is needed
            - Respect privacy and confidentiality
            """,
            tools=["email_classifier", "sentiment_analyzer", "response_generator", "escalation_detector"]
        )
        super().__init__(config)
        self._response_templates = self._load_response_templates()
        self._escalation_keywords = self._load_escalation_keywords()

    def _load_response_templates(self) -> Dict[str, str]:
        """Load email response templates"""
        return {
            "customer_inquiry": """
            Dear {sender_name},

            Thank you for your inquiry about {topic}. We appreciate you reaching out to us.

            {main_response}

            If you have any additional questions, please don't hesitate to contact us.

            Best regards,
            {signature}
            """,

            "support_request": """
            Dear {sender_name},

            Thank you for contacting our support team. We have received your request regarding {issue}.

            {resolution_steps}

            We are committed to resolving this matter promptly. If you need immediate assistance, please contact us at {support_contact}.

            Best regards,
            {support_signature}
            """,

            "sales_lead": """
            Dear {sender_name},

            Thank you for your interest in {product_service}. We're excited to help you find the right solution for your needs.

            {value_proposition}

            I would love to schedule a brief call to discuss your requirements in more detail. Are you available for a 15-minute conversation this week?

            Best regards,
            {sales_signature}
            """,

            "complaint": """
            Dear {sender_name},

            Thank you for bringing this matter to our attention. We sincerely apologize for any inconvenience you have experienced.

            {acknowledgment}

            We take all feedback seriously and are committed to making this right. A member of our team will contact you within 24 hours to discuss this further.

            Sincerely,
            {management_signature}
            """,

            "feedback": """
            Dear {sender_name},

            Thank you for taking the time to share your feedback with us. Your input is invaluable in helping us improve our {product_service}.

            {feedback_acknowledgment}

            We truly appreciate customers like you who help us grow and improve.

            Best regards,
            {signature}
            """,

            "auto_reply": """
            Thank you for your email. We have received your message and will respond within {response_time}.

            For urgent matters, please contact us at {urgent_contact}.

            Best regards,
            {company_name} Team
            """
        }

    def _load_escalation_keywords(self) -> Dict[str, List[str]]:
        """Load keywords that trigger escalation"""
        return {
            "urgent": ["urgent", "emergency", "asap", "immediately", "crisis", "critical"],
            "negative": ["angry", "frustrated", "disappointed", "terrible", "awful", "horrible"],
            "legal": ["lawsuit", "legal action", "attorney", "lawyer", "sue", "court"],
            "security": ["breach", "hack", "security", "compromise", "unauthorized", "fraud"],
            "executive": ["ceo", "president", "director", "executive", "manager", "supervisor"],
            "cancellation": ["cancel", "refund", "terminate", "end service", "close account"]
        }

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """Execute email processing task"""

        # Parse email data from task
        email_data = await self._parse_email_data(task, kwargs)

        # Analyze the email
        analysis = await self._analyze_email(email_data, context)

        # Determine response action
        response_plan = await self._determine_response_action(analysis, email_data, context)

        # Generate response based on action
        if response_plan.action == ResponseAction.AUTO_REPLY:
            result = await self._generate_auto_reply(email_data, analysis, context)
        elif response_plan.action == ResponseAction.DRAFT_RESPONSE:
            result = await self._generate_draft_response(email_data, analysis, context)
        elif response_plan.action == ResponseAction.FORWARD_TO_HUMAN:
            result = await self._prepare_human_handoff(email_data, analysis, response_plan)
        elif response_plan.action == ResponseAction.ESCALATE:
            result = await self._handle_escalation(email_data, analysis, response_plan)
        else:
            result = await self._categorize_email(email_data, analysis)

        return result

    async def _parse_email_data(self, task: str, kwargs: Dict[str, Any]) -> EmailData:
        """Parse email data from task input"""

        # If email data is provided in kwargs, use it
        if "email_data" in kwargs:
            email_dict = kwargs["email_data"]
            return EmailData(
                subject=email_dict.get("subject", ""),
                sender=email_dict.get("sender", ""),
                recipients=email_dict.get("recipients", []),
                body=email_dict.get("body", ""),
                timestamp=datetime.fromisoformat(email_dict.get("timestamp", datetime.now().isoformat())),
                thread_id=email_dict.get("thread_id"),
                attachments=email_dict.get("attachments", []),
                html_body=email_dict.get("html_body"),
                headers=email_dict.get("headers", {})
            )

        # Otherwise, try to parse from task text
        parsing_prompt = f"""
        Extract email information from this text:

        {task}

        Extract in JSON format:
        {{
            "subject": "email subject",
            "sender": "sender email or name",
            "recipients": ["recipient1", "recipient2"],
            "body": "email body content",
            "timestamp": "2024-01-01T12:00:00"
        }}
        """

        try:
            response = await self.generate_llm_response(
                parsing_prompt, TaskType.DATA_ANALYSIS
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                email_dict = json.loads(json_match.group())
                return EmailData(
                    subject=email_dict.get("subject", ""),
                    sender=email_dict.get("sender", ""),
                    recipients=email_dict.get("recipients", []),
                    body=email_dict.get("body", task),  # Fallback to task as body
                    timestamp=datetime.now(),
                    attachments=[]
                )

        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: treat entire task as email body
        return EmailData(
            subject="Email Processing Request",
            sender="unknown@example.com",
            recipients=["support@company.com"],
            body=task,
            timestamp=datetime.now(),
            attachments=[]
        )

    async def _analyze_email(self, email_data: EmailData, context: AgentContext) -> EmailAnalysis:
        """Analyze email content and classify it"""

        analysis_prompt = f"""
        Analyze this email and provide classification:

        Subject: {email_data.subject}
        From: {email_data.sender}
        Body: {email_data.body}

        Provide analysis in JSON format:
        {{
            "email_type": "customer_inquiry|support_request|sales_lead|internal_communication|vendor_communication|marketing_response|complaint|feedback|spam|general",
            "priority": "urgent|high|normal|low",
            "sentiment": "positive|neutral|negative",
            "intent": "brief description of sender's intent",
            "key_topics": ["topic1", "topic2", "topic3"],
            "action_required": true/false,
            "urgency_indicators": ["indicator1", "indicator2"],
            "business_impact": "high|medium|low",
            "confidence_score": 0.85
        }}
        """

        try:
            response = await self.generate_llm_response(
                analysis_prompt, TaskType.DATA_ANALYSIS
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis_dict = json.loads(json_match.group())

                return EmailAnalysis(
                    email_type=EmailType(analysis_dict.get("email_type", "general")),
                    priority=EmailPriority(analysis_dict.get("priority", "normal")),
                    sentiment=analysis_dict.get("sentiment", "neutral"),
                    intent=analysis_dict.get("intent", "General inquiry"),
                    key_topics=analysis_dict.get("key_topics", []),
                    action_required=analysis_dict.get("action_required", True),
                    urgency_indicators=analysis_dict.get("urgency_indicators", []),
                    business_impact=analysis_dict.get("business_impact", "medium"),
                    confidence_score=analysis_dict.get("confidence_score", 0.7)
                )

        except (json.JSONDecodeError, Exception):
            pass

        # Fallback analysis
        return EmailAnalysis(
            email_type=EmailType.GENERAL,
            priority=EmailPriority.NORMAL,
            sentiment="neutral",
            intent="General inquiry",
            key_topics=[],
            action_required=True,
            urgency_indicators=[],
            business_impact="medium",
            confidence_score=0.5
        )

    async def _determine_response_action(
        self,
        analysis: EmailAnalysis,
        email_data: EmailData,
        context: AgentContext
    ) -> EmailResponse:
        """Determine the appropriate response action"""

        # Check for escalation triggers
        escalation_triggered = await self._check_escalation_triggers(analysis, email_data)

        if escalation_triggered:
            action = ResponseAction.ESCALATE
        elif analysis.priority == EmailPriority.URGENT:
            action = ResponseAction.DRAFT_RESPONSE
        elif analysis.email_type == EmailType.SPAM:
            action = ResponseAction.IGNORE
        elif analysis.email_type in [EmailType.COMPLAINT, EmailType.SUPPORT_REQUEST]:
            action = ResponseAction.FORWARD_TO_HUMAN
        elif analysis.email_type == EmailType.CUSTOMER_INQUIRY and analysis.business_impact == "low":
            action = ResponseAction.AUTO_REPLY
        else:
            action = ResponseAction.DRAFT_RESPONSE

        return EmailResponse(
            action=action,
            draft_subject=None,
            draft_body=None,
            recipient=email_data.sender,
            cc_recipients=[],
            suggested_tone="professional",
            escalation_reason=escalation_triggered if escalation_triggered else None,
            follow_up_required=analysis.priority in [EmailPriority.URGENT, EmailPriority.HIGH],
            follow_up_date=datetime.now() + timedelta(days=1) if analysis.action_required else None,
            internal_notes=None
        )

    async def _check_escalation_triggers(
        self,
        analysis: EmailAnalysis,
        email_data: EmailData
    ) -> Optional[str]:
        """Check if email should be escalated"""

        email_text = f"{email_data.subject} {email_data.body}".lower()

        # Check for escalation keywords
        for category, keywords in self._escalation_keywords.items():
            for keyword in keywords:
                if keyword in email_text:
                    return f"Escalation triggered by {category} keywords: {keyword}"

        # Check for multiple urgency indicators
        if len(analysis.urgency_indicators) >= 3:
            return "Multiple urgency indicators detected"

        # Check for negative sentiment with high business impact
        if analysis.sentiment == "negative" and analysis.business_impact == "high":
            return "High-impact negative sentiment"

        return None

    async def _generate_auto_reply(
        self,
        email_data: EmailData,
        analysis: EmailAnalysis,
        context: AgentContext
    ) -> str:
        """Generate automated reply"""

        # Get business context for personalization
        business_context = await self._get_business_context(context)

        template = self._response_templates["auto_reply"]

        auto_reply = template.format(
            response_time="24 hours",
            urgent_contact=business_context.get("support_contact", "support@company.com"),
            company_name=business_context.get("company_name", "Our Company")
        )

        result = f"""
        📧 **AUTO-REPLY GENERATED**

        **To:** {email_data.sender}
        **Subject:** Re: {email_data.subject}

        **Message:**
        {auto_reply}

        **Analysis:**
        - Type: {analysis.email_type.value}
        - Priority: {analysis.priority.value}
        - Sentiment: {analysis.sentiment}
        - Action Required: {analysis.action_required}

        **Recommendation:** This email has been automatically acknowledged. A team member will follow up within the specified timeframe.
        """

        return result

    async def _generate_draft_response(
        self,
        email_data: EmailData,
        analysis: EmailAnalysis,
        context: AgentContext
    ) -> str:
        """Generate draft response for human review"""

        # Get business context
        business_context = await self._get_business_context(context)

        # Build response generation prompt
        response_prompt = f"""
        Generate a professional email response based on this analysis:

        Original Email:
        Subject: {email_data.subject}
        From: {email_data.sender}
        Body: {email_data.body}

        Analysis:
        - Type: {analysis.email_type.value}
        - Intent: {analysis.intent}
        - Sentiment: {analysis.sentiment}
        - Key Topics: {', '.join(analysis.key_topics)}

        Business Context:
        {json.dumps(business_context, indent=2)}

        Generate a response that:
        1. Addresses the sender's specific concerns or questions
        2. Maintains a {self._get_appropriate_tone(analysis)} tone
        3. Provides helpful and accurate information
        4. Includes appropriate next steps or actions
        5. Reflects the company's brand voice and values

        Format as a complete email with subject and body.
        """

        draft_response = await self.generate_llm_response(
            response_prompt, TaskType.REALTIME_CHAT
        )

        result = f"""
        📝 **DRAFT RESPONSE GENERATED**

        **Original Email Analysis:**
        - Type: {analysis.email_type.value}
        - Priority: {analysis.priority.value}
        - Sentiment: {analysis.sentiment}
        - Confidence: {analysis.confidence_score:.2f}

        **Generated Response:**
        {draft_response}

        **Recommendations:**
        - Review for accuracy and brand alignment
        - Verify any specific claims or promises
        - Consider adding personal touch if appropriate
        - {'Schedule follow-up' if analysis.action_required else 'No follow-up needed'}
        """

        return result

    async def _prepare_human_handoff(
        self,
        email_data: EmailData,
        analysis: EmailAnalysis,
        response_plan: EmailResponse
    ) -> str:
        """Prepare email for human handling"""

        result = f"""
        👤 **HUMAN INTERVENTION REQUIRED**

        **Email Summary:**
        - From: {email_data.sender}
        - Subject: {email_data.subject}
        - Type: {analysis.email_type.value}
        - Priority: {analysis.priority.value}
        - Sentiment: {analysis.sentiment}

        **Key Points:**
        - Intent: {analysis.intent}
        - Topics: {', '.join(analysis.key_topics)}
        - Action Required: {analysis.action_required}

        **Recommendation:** This email requires human attention due to:
        - Complex inquiry requiring expertise
        - Sensitive customer issue
        - Potential business impact: {analysis.business_impact}

        **Suggested Next Steps:**
        1. Assign to appropriate team member
        2. Respond within {'2 hours' if analysis.priority == EmailPriority.URGENT else '24 hours'}
        3. {'Follow up required' if response_plan.follow_up_required else 'One-time response sufficient'}

        **Original Email:**
        {email_data.body}
        """

        return result

    async def _handle_escalation(
        self,
        email_data: EmailData,
        analysis: EmailAnalysis,
        response_plan: EmailResponse
    ) -> str:
        """Handle escalated emails"""

        result = f"""
        🚨 **ESCALATION ALERT**

        **URGENT: Email requires immediate attention**

        **Escalation Reason:** {response_plan.escalation_reason}

        **Email Details:**
        - From: {email_data.sender}
        - Subject: {email_data.subject}
        - Priority: {analysis.priority.value}
        - Sentiment: {analysis.sentiment}
        - Business Impact: {analysis.business_impact}

        **Urgency Indicators:**
        {chr(10).join(f'• {indicator}' for indicator in analysis.urgency_indicators)}

        **Recommended Actions:**
        1. 🔥 Immediate acknowledgment (within 1 hour)
        2. 📞 Consider phone call if appropriate
        3. 👥 Involve management/specialist team
        4. 📋 Document resolution steps
        5. 🔄 Follow up to ensure satisfaction

        **Original Email:**
        {email_data.body}

        **⚠️ Note: This email has been flagged for executive attention.**
        """

        return result

    async def _categorize_email(
        self,
        email_data: EmailData,
        analysis: EmailAnalysis
    ) -> str:
        """Categorize email without generating response"""

        result = f"""
        📊 **EMAIL CATEGORIZED**

        **Classification Results:**
        - Type: {analysis.email_type.value}
        - Priority: {analysis.priority.value}
        - Sentiment: {analysis.sentiment}
        - Business Impact: {analysis.business_impact}
        - Confidence: {analysis.confidence_score:.2f}

        **Content Analysis:**
        - Intent: {analysis.intent}
        - Key Topics: {', '.join(analysis.key_topics)}
        - Action Required: {'Yes' if analysis.action_required else 'No'}

        **Email Filed Under:** {analysis.email_type.value.replace('_', ' ').title()}

        **Next Steps:** Email has been categorized and routed to the appropriate team.
        """

        return result

    def _get_appropriate_tone(self, analysis: EmailAnalysis) -> str:
        """Determine appropriate response tone"""

        if analysis.email_type == EmailType.COMPLAINT:
            return "empathetic and professional"
        elif analysis.email_type == EmailType.SALES_LEAD:
            return "enthusiastic and professional"
        elif analysis.sentiment == "negative":
            return "understanding and helpful"
        elif analysis.priority == EmailPriority.URGENT:
            return "prompt and professional"
        else:
            return "friendly and professional"

    async def _get_business_context(self, context: AgentContext) -> Dict[str, Any]:
        """Get business context for email responses"""

        # Default business context
        business_context = {
            "company_name": "Our Company",
            "support_contact": "support@company.com",
            "website": "www.company.com",
            "business_hours": "Monday-Friday, 9 AM - 5 PM",
            "response_commitment": "24 hours"
        }

        # Try to get actual business context
        if context.business_context and context.business_context.get("retrieved_contexts"):
            for ctx in context.business_context["retrieved_contexts"]:
                content = ctx.get("content", "").lower()

                # Extract company information
                if "company" in content or "business" in content:
                    # This would extract real business details
                    pass

        return business_context

    async def process_email_batch(
        self,
        emails: List[EmailData],
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """Process multiple emails in batch"""

        results = []

        # Process emails concurrently
        tasks = []
        for email in emails:
            task = self._process_single_email(email, context)
            tasks.append(task)

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                results.append({
                    "email_index": i,
                    "status": "error",
                    "error": str(result),
                    "email": emails[i]
                })
            else:
                results.append({
                    "email_index": i,
                    "status": "processed",
                    "result": result,
                    "email": emails[i]
                })

        return results

    async def _process_single_email(
        self,
        email_data: EmailData,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Process a single email"""

        analysis = await self._analyze_email(email_data, context)
        response_plan = await self._determine_response_action(analysis, email_data, context)

        return {
            "analysis": analysis,
            "response_plan": response_plan,
            "processing_time": datetime.now()
        }

    def _get_tool_function(self, tool_name: str):
        """Get email-specific tool functions"""
        tools = {
            "email_classifier": self._analyze_email,
            "sentiment_analyzer": self._analyze_sentiment,
            "response_generator": self._generate_draft_response,
            "escalation_detector": self._check_escalation_triggers
        }
        return tools.get(tool_name)

    async def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of email text"""

        sentiment_prompt = f"""
        Analyze the sentiment of this email text:

        {text}

        Provide analysis in JSON format:
        {{
            "sentiment": "positive|neutral|negative",
            "confidence": 0.85,
            "emotional_indicators": ["indicator1", "indicator2"],
            "tone": "formal|casual|urgent|friendly|angry"
        }}
        """

        try:
            response = await self.generate_llm_response(
                sentiment_prompt, TaskType.DATA_ANALYSIS
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except (json.JSONDecodeError, Exception):
            pass

        return {
            "sentiment": "neutral",
            "confidence": 0.5,
            "emotional_indicators": [],
            "tone": "formal"
        }