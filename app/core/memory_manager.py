from typing import Dict, List, Any, Optional
import json
import time
import hashlib
from datetime import datetime, timedelta

import redis.asyncio as redis
from langchain.memory import ConversationSummaryBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.schema.document import Document

from app.config import settings
from app.core.embeddings import embedding_manager
from app.core.multi_llm_router import llm_router, TaskType
from app.utils.exceptions import VectorStoreException


class ConversationMemory:
    """Manages conversation memory with both short-term and long-term storage"""

    def __init__(self, organization_id: str, agent_id: str):
        self.organization_id = organization_id
        self.agent_id = agent_id
        self.redis_client = None
        self.conversation_memory = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize Redis and conversation memory"""
        try:
            self.redis_client = redis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            raise VectorStoreException(f"Failed to connect to Redis: {str(e)}")

        # Initialize conversation buffer memory
        try:
            # Use the router to get an LLM for summarization
            self.conversation_memory = ConversationSummaryBufferMemory(
                llm=llm_router.clients.get("gpt-4-mini") or list(llm_router.clients.values())[0],
                max_token_limit=2000,
                return_messages=True
            )
        except Exception as e:
            # Fallback to simple buffer if LLM not available
            from langchain.memory import ConversationBufferWindowMemory
            self.conversation_memory = ConversationBufferWindowMemory(
                k=10,
                return_messages=True
            )

    async def store_interaction(
        self,
        session_id: str,
        user_input: str,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a conversation interaction in both short-term and long-term memory

        Args:
            session_id: Unique session identifier
            user_input: User's input message
            agent_response: Agent's response
            metadata: Additional metadata about the interaction

        Returns:
            Success status
        """
        try:
            timestamp = int(time.time())
            interaction = {
                "session_id": session_id,
                "user_input": user_input,
                "agent_response": agent_response,
                "timestamp": timestamp,
                "metadata": metadata or {}
            }

            # Store in short-term memory (Redis)
            await self._store_short_term(session_id, interaction)

            # Add to conversation buffer
            self.conversation_memory.chat_memory.add_user_message(user_input)
            self.conversation_memory.chat_memory.add_ai_message(agent_response)

            # Store important interactions in long-term memory (vector store)
            if self._is_interaction_important(user_input, agent_response, metadata):
                await self._store_long_term(interaction)

            return True

        except Exception as e:
            print(f"Error storing interaction: {str(e)}")
            return False

    async def _store_short_term(self, session_id: str, interaction: Dict[str, Any]):
        """Store interaction in Redis for short-term access"""
        # Session-specific key
        session_key = f"session:{self.organization_id}:{self.agent_id}:{session_id}"

        # Store interaction in a list for the session
        await self.redis_client.lpush(session_key, json.dumps(interaction))

        # Keep only last 50 interactions per session
        await self.redis_client.ltrim(session_key, 0, 49)

        # Set expiration (24 hours)
        await self.redis_client.expire(session_key, 86400)

        # Also store in recent interactions key for cross-session access
        recent_key = f"recent:{self.organization_id}:{self.agent_id}"
        await self.redis_client.lpush(recent_key, json.dumps(interaction))
        await self.redis_client.ltrim(recent_key, 0, 99)  # Keep last 100
        await self.redis_client.expire(recent_key, 86400)

    async def _store_long_term(self, interaction: Dict[str, Any]):
        """Store important interactions in vector store for long-term retrieval"""
        try:
            collection_name = f"memory_{self.organization_id}"

            # Create collection if it doesn't exist
            await embedding_manager.create_collection(collection_name)

            # Create a comprehensive document for embedding
            content = f"""
            User Query: {interaction['user_input']}
            Agent Response: {interaction['agent_response']}
            Context: This interaction occurred on {datetime.fromtimestamp(interaction['timestamp']).isoformat()}
            """

            metadata = {
                **interaction.get('metadata', {}),
                'interaction_type': 'conversation',
                'agent_id': self.agent_id,
                'session_id': interaction['session_id'],
                'timestamp': interaction['timestamp'],
                'user_input': interaction['user_input'],
                'agent_response': interaction['agent_response']
            }

            document = {
                "id": self._generate_interaction_id(interaction),
                "content": content.strip(),
                "metadata": metadata
            }

            await embedding_manager.add_documents(collection_name, [document])

        except Exception as e:
            print(f"Error storing long-term memory: {str(e)}")

    def _is_interaction_important(
        self,
        user_input: str,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Determine if an interaction should be stored in long-term memory"""
        metadata = metadata or {}

        # Store if explicitly marked as important
        if metadata.get("important", False):
            return True

        # Store if it contains business-critical information
        business_keywords = [
            "policy", "procedure", "pricing", "product", "service",
            "support", "complaint", "feedback", "issue", "problem",
            "account", "billing", "order", "purchase", "refund"
        ]

        text_to_check = f"{user_input} {agent_response}".lower()
        if any(keyword in text_to_check for keyword in business_keywords):
            return True

        # Store longer interactions (likely more substantive)
        if len(user_input) + len(agent_response) > 200:
            return True

        # Store if it contains contact information or specific details
        if any(pattern in text_to_check for pattern in ["@", "phone", "address", "email"]):
            return True

        return False

    def _generate_interaction_id(self, interaction: Dict[str, Any]) -> str:
        """Generate a unique ID for an interaction"""
        content = f"{interaction['session_id']}{interaction['timestamp']}{interaction['user_input']}"
        return hashlib.md5(content.encode()).hexdigest()

    async def retrieve_session_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a specific session"""
        try:
            session_key = f"session:{self.organization_id}:{self.agent_id}:{session_id}"
            interactions = await self.redis_client.lrange(session_key, 0, limit - 1)

            return [json.loads(interaction) for interaction in interactions]

        except Exception as e:
            print(f"Error retrieving session history: {str(e)}")
            return []

    async def retrieve_relevant_context(
        self,
        query: str,
        top_k: int = 5,
        time_range_hours: int = 24
    ) -> List[Document]:
        """
        Retrieve relevant context from long-term memory

        Args:
            query: Query to search for relevant context
            top_k: Number of results to return
            time_range_hours: Only consider interactions within this time range

        Returns:
            List of relevant documents
        """
        try:
            collection_name = f"memory_{self.organization_id}"

            # Calculate time threshold
            time_threshold = int(time.time()) - (time_range_hours * 3600)

            # Search for relevant interactions
            results = await embedding_manager.search_similar(
                collection_name=collection_name,
                query=query,
                limit=top_k,
                score_threshold=0.7,
                filter_conditions={
                    "agent_id": self.agent_id,
                    "interaction_type": "conversation"
                }
            )

            # Filter by time range and convert to Documents
            relevant_docs = []
            for result in results:
                if result["metadata"].get("timestamp", 0) >= time_threshold:
                    doc = Document(
                        page_content=result["content"],
                        metadata=result["metadata"]
                    )
                    relevant_docs.append(doc)

            return relevant_docs

        except Exception as e:
            print(f"Error retrieving relevant context: {str(e)}")
            return []

    async def get_conversation_summary(self, session_id: str) -> str:
        """Get a summary of the conversation"""
        try:
            history = await self.retrieve_session_history(session_id)

            if not history:
                return "No conversation history available."

            # Use the conversation memory to generate summary
            if hasattr(self.conversation_memory, 'predict_new_summary'):
                # Build conversation for summary
                messages = []
                for interaction in reversed(history[-10:]):  # Last 10 interactions
                    messages.append(f"User: {interaction['user_input']}")
                    messages.append(f"Assistant: {interaction['agent_response']}")

                conversation_text = "\n".join(messages)
                return await self.conversation_memory.predict_new_summary(
                    messages=[],
                    new_lines=conversation_text
                )
            else:
                # Simple fallback summary
                return f"Conversation with {len(history)} interactions covering various topics."

        except Exception as e:
            print(f"Error generating conversation summary: {str(e)}")
            return "Unable to generate conversation summary."

    async def update_business_context(
        self,
        new_information: Dict[str, Any],
        source: str = "conversation"
    ):
        """
        Update business context with new information learned from conversations

        Args:
            new_information: New information to store
            source: Source of the information
        """
        try:
            collection_name = f"context_{self.organization_id}"

            # Create collection if it doesn't exist
            await embedding_manager.create_collection(collection_name)

            # Create document for the new information
            content = f"""
            New Business Information:
            {json.dumps(new_information, indent=2)}

            Source: {source}
            Learned on: {datetime.now().isoformat()}
            """

            metadata = {
                "information_type": "business_context_update",
                "source": source,
                "timestamp": int(time.time()),
                "agent_id": self.agent_id,
                **new_information
            }

            document = {
                "id": f"context_update_{int(time.time())}_{source}",
                "content": content.strip(),
                "metadata": metadata
            }

            await embedding_manager.add_documents(collection_name, [document])

        except Exception as e:
            print(f"Error updating business context: {str(e)}")

    async def clear_session_memory(self, session_id: str) -> bool:
        """Clear memory for a specific session"""
        try:
            session_key = f"session:{self.organization_id}:{self.agent_id}:{session_id}"
            await self.redis_client.delete(session_key)
            return True
        except Exception as e:
            print(f"Error clearing session memory: {str(e)}")
            return False

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about memory usage"""
        try:
            # Count recent interactions
            recent_key = f"recent:{self.organization_id}:{self.agent_id}"
            recent_count = await self.redis_client.llen(recent_key)

            # Get long-term memory stats
            collection_name = f"memory_{self.organization_id}"
            try:
                collection_info = await embedding_manager.get_collection_info(collection_name)
                long_term_count = collection_info.get("points_count", 0)
            except:
                long_term_count = 0

            return {
                "recent_interactions": recent_count,
                "long_term_interactions": long_term_count,
                "organization_id": self.organization_id,
                "agent_id": self.agent_id
            }

        except Exception as e:
            print(f"Error getting memory stats: {str(e)}")
            return {}


class MemoryManager:
    """Global memory manager for handling multiple conversation memories"""

    def __init__(self):
        self.conversation_memories: Dict[str, ConversationMemory] = {}

    def get_conversation_memory(
        self,
        organization_id: str,
        agent_id: str
    ) -> ConversationMemory:
        """Get or create conversation memory for an organization/agent pair"""
        key = f"{organization_id}:{agent_id}"

        if key not in self.conversation_memories:
            self.conversation_memories[key] = ConversationMemory(
                organization_id, agent_id
            )

        return self.conversation_memories[key]

    async def cleanup_old_memories(self, days_old: int = 30):
        """Clean up old memories to save storage"""
        cutoff_time = int(time.time()) - (days_old * 24 * 3600)

        # This would implement cleanup logic for old interactions
        # For now, Redis TTL handles short-term cleanup
        # Long-term cleanup would require querying vector store
        pass


# Global memory manager instance
memory_manager = MemoryManager()