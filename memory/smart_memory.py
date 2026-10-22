"""IRIS v1 Hybrid Smart Memory — Vector + Episodic + Semantic Memory"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from config import config
from core.db import db

class SmartMemory:
    """
    Three-layer memory system:
    1. Semantic Memory — Facts, concepts, knowledge (key-value + vectors)
    2. Episodic Memory — Events, experiences, what happened
    3. Working Memory — Current context, recent conversation
    """

    def __init__(self):
        self.encoder = None
        self._init_encoder()

    def _init_encoder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            # Don't crash if sentence_transformers isn't installed —
            # also don't crash if db.log() fails (tables might not exist yet)
            try:
                db.log("WARNING", "smart_memory", f"Encoder init failed: {e}")
            except Exception:
                pass

    def learn_about_owner(self, fact: str, category: str = "general", importance: int = 5) -> bool:
        """Learn something new about the owner"""
        key = self._generate_key(fact)

        # Check if similar fact exists
        existing = db.search_memory(key, category=category, limit=1)
        if existing:
            # Update existing with more detail
            old = existing[0]
            combined = f"{old['value']} | Updated: {fact}"
            db.save_memory(key, combined, category, importance, source="owner_interaction")
        else:
            db.save_memory(key, fact, category, importance, source="owner_interaction")

        # Also write to markdown file for persistence
        self._write_to_file(fact, category)

        return True

    def recall(self, query: str, category: str = None, limit: int = 10) -> List[Dict]:
        """Recall memories matching query"""
        # Database search
        results = db.search_memory(query, category=category, limit=limit)

        # Semantic search if encoder available
        if self.encoder and query:
            try:
                query_vec = self.encoder.encode([query])
                # Could add vector similarity here
                pass
            except:
                pass

        return results

    def remember_event(self, event: str, context: str = None, emotion: str = "neutral", lesson: str = None):
        """Store an episodic memory (something that happened)"""
        db.save_episode(event, context, emotion, lesson)

    def get_owner_profile(self) -> Dict:
        """Get complete owner profile"""
        profile = db.get_owner()
        if not profile:
            return {}

        # Parse JSON fields
        for field in ['preferences', 'personality_notes', 'tech_stack_prefs', 'project_history', 'secrets']:
            if profile.get(field):
                try:
                    profile[field] = json.loads(profile[field])
                except:
                    pass

        # Add recent memories
        profile['recent_memories'] = db.search_memory("", limit=20)
        profile['recent_episodes'] = db.get_episodes(limit=10)

        return profile

    def update_owner_profile(self, **kwargs) -> bool:
        """Update owner profile with new information"""
        db.update_owner(**kwargs)
        return True

    def extract_facts(self, text: str) -> List[str]:
        """Extract factual statements from text using AI"""
        try:
            from core.aevibron_client import aevibron
            prompt = f"""Extract factual statements about the user from this text. 
Return as a JSON array of strings. Only extract clear facts, not opinions or questions.

Text: {text}

Facts:"""

            response = aevibron.fast_response(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "[]")

            # Try to parse JSON
            try:
                facts = json.loads(content)
                if isinstance(facts, list):
                    return facts
            except:
                # Extract lines that look like facts
                lines = [l.strip("- ").strip() for l in content.split("\n") if l.strip().startswith("-")]
                return lines
        except Exception as e:
            db.log("WARNING", "smart_memory", f"Fact extraction failed: {e}")

        return []

    def get_concept_graph(self, concept: str) -> Dict:
        """Get related concepts and memories"""
        memories = db.search_memory(concept, limit=20)

        # Group by category
        categories = {}
        for m in memories:
            cat = m.get('category', 'general')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)

        return {
            "concept": concept,
            "total_memories": len(memories),
            "categories": categories,
            "related_concepts": self._find_related(concept, memories)
        }

    def _find_related(self, concept: str, memories: List[Dict]) -> List[str]:
        """Find related concepts from memories"""
        related = set()
        for m in memories:
            value = m.get('value', '')
            # Simple word extraction
            words = re.findall(r'\b[A-Z][a-z]{2,}\b', value)
            related.update(words)

        # Remove the concept itself
        related.discard(concept.capitalize())
        return list(related)[:10]

    def _generate_key(self, fact: str) -> str:
        """Generate a key for storing a fact"""
        # Extract subject
        words = fact.lower().split()
        if len(words) > 3:
            key = "_".join(words[:3])
        else:
            key = "_".join(words)
        key = re.sub(r'[^\w]', '_', key)[:50]
        return key

    def _write_to_file(self, fact: str, category: str):
        """Write fact to markdown file for persistence"""
        try:
            import os
            from datetime import datetime

            file_path = os.path.join(config.LEARNINGS_DIR, f"{category}.md")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n- [{datetime.now().isoformat()}] {fact}\n")
        except Exception as e:
            db.log("WARNING", "smart_memory", f"Failed to write to file: {e}")

    def get_learning_files(self) -> List[str]:
        """Get list of all learning markdown files"""
        import os
        if os.path.exists(config.LEARNINGS_DIR):
            return [f for f in os.listdir(config.LEARNINGS_DIR) if f.endswith('.md')]
        return []

    def read_learning_file(self, category: str) -> str:
        """Read a learning file"""
        import os
        file_path = os.path.join(config.LEARNINGS_DIR, f"{category}.md")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def consolidate_memories(self):
        """Consolidate and clean up memories periodically"""
        # This could run as a background task
        # Find duplicate memories and merge them
        # Remove low-importance old memories
        pass

# Singleton
smart_memory = SmartMemory()
