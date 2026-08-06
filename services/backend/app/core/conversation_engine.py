"""
KUDOS Conversational AI Engine v2
Responds like a real human — contextual, concise, empathetic.
"""
import re
import random
from typing import Optional


# ──────────────────────────────────────────────
# CONVERSATION CONTEXT
# ──────────────────────────────────────────────

_contexts: dict[int, dict] = {}


def _get_ctx(conv_id: int) -> dict:
    if conv_id not in _contexts:
        _contexts[conv_id] = {"topics": [], "mood": "neutral", "count": 0, "name": None, "last_query": ""}
    return _contexts[conv_id]


# ──────────────────────────────────────────────
# DETECT QUERY TYPE
# ──────────────────────────────────────────────

GREETING_PATTERNS = [
    r"^(hi|hello|hey|yo|sup|howdy|greetings|good morning|good afternoon|good evening|hola)\b",
    r"^(how are you|how's it going|what's up|how do you do|nice to meet)",
    r"^(who are you|what are you|tell me about yourself|what can you do|introduce yourself)",
    r"^(bye|goodbye|see you|later|take care|good night)",
    r"^(thanks|thank you|thx|cheers|appreciate)",
    r"^(yes|no|ok|okay|sure|right|yep|nope|yeah)",
    r"^(lol|haha|wow|cool|nice|great|awesome|amazing)",
]

MOOD_PATTERNS = {
    "stressed": [r"stress", r"anxious", r"worried", r"overwhelm", r"pressure", r"nervous"],
    "sad": [r"sad", r"depressed", r"lonely", r"unhappy", r"miserable", r"heartbroken"],
    "frustrated": [r"frustrated", r"annoyed", r"angry", r"irritated", r"stuck", r"confused"],
    "happy": [r"happy", r"excited", r"great", r"awesome", r"amazing", r"love", r"fantastic"],
    "tired": [r"tired", r"exhausted", r"sleepy", r"burned out", r"fatigue"],
}


def _detect_query_type(query: str) -> str:
    q = query.lower().strip()
    for pattern in GREETING_PATTERNS:
        if re.search(pattern, q):
            return "greeting"
    if len(q.split()) <= 3 and not any(w in q for w in ["what", "how", "why", "when", "where", "who"]):
        return "casual"
    return "question"


def _detect_mood(query: str) -> Optional[str]:
    q = query.lower()
    for mood, patterns in MOOD_PATTERNS.items():
        for p in patterns:
            if re.search(p, q):
                return mood
    return None


def _extract_relevant_sentences(query: str, text: str, max_sentences: int = 4) -> str:
    """Extract the most relevant sentences from a text based on query keywords."""
    query_words = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
    stop = {"the", "and", "for", "that", "this", "with", "from", "are", "was", "were", "have", "has", "had", "not", "but", "can", "will", "would", "could", "should", "how", "what", "when", "where", "which", "who", "why", "tell", "give", "show", "explain", "help", "about"}
    query_words -= stop

    sentences = re.split(r'[.!?\n]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return text[:300]

    # Score each sentence by keyword overlap
    scored = []
    for sent in sentences:
        sent_words = set(re.findall(r"[a-zA-Z]{3,}", sent.lower()))
        overlap = len(query_words & sent_words)
        scored.append((overlap, sent))

    scored.sort(key=lambda x: -x[0])

    # Take top relevant sentences
    result = []
    for _, sent in scored[:max_sentences]:
        result.append(sent)

    return ". ".join(result) + "."


# ──────────────────────────────────────────────
# GREETING RESPONSES
# ──────────────────────────────────────────────

def _greeting_response(query: str, ctx: dict) -> str:
    q = query.lower().strip()
    name = ctx.get("name")
    name_str = f", {name}" if name else ""

    if re.search(r"^(hi|hello|hey|yo|sup|howdy|greetings)", q):
        return random.choice([
            f"Hey{name_str}! 👋 How can I help you today?",
            f"Hi{name_str}! What's on your mind?",
            f"Hello{name_str}! 😊 What would you like to know?",
            f"Hey there{name_str}! Ask me anything — I'm here to help.",
        ])

    if re.search(r"how are you|how's it going|what's up", q):
        return random.choice([
            "I'm doing great, thanks for asking! 😊 How about you?",
            "I'm good! Ready to help with whatever you need. What's up?",
            "All good on my end! What can I do for you today?",
        ])

    if re.search(r"who are you|what are you|tell me about yourself", q):
        return (
            "I'm KUDOS 🧠 — your AI knowledge assistant for Digital Campus!\n\n"
            "Here's what I can do:\n"
            "• Answer questions from my knowledge base (documents, web pages, connectors)\n"
            "• Help you study, find information, and learn new topics\n"
            "• Search the web and Wikipedia for answers\n"
            "• Chat naturally — I understand context and emotions\n\n"
            "Just ask me anything! I learn from every conversation. 😊"
        )

    if re.search(r"thanks|thank you|thx|cheers", q):
        return random.choice([
            "You're welcome! 😊 Anything else I can help with?",
            "Happy to help! Let me know if you need anything else.",
            "Anytime! That's what I'm here for. 🙌",
        ])

    if re.search(r"bye|goodbye|see you|later", q):
        return random.choice([
            "See you later! 👋 Take care!",
            "Bye! Good luck with everything! 🙌",
            "Until next time! Don't hesitate to come back if you need help. 😊",
        ])

    if re.search(r"^(yes|no|ok|okay|sure|right|yep)", q):
        return random.choice([
            "Got it! What else would you like to know?",
            "Sure thing! What's next?",
            "👍 Anything else?",
        ])

    return f"Hey{name_str}! What would you like to know? I'm here to help. 😊"


def _mood_response(mood: str, query: str) -> str:
    responses = {
        "stressed": [
            "I hear you — stress can be really tough. 💙 Take a deep breath. What's weighing on you? Maybe I can help break it down into manageable pieces.",
            "Stress is hard, but you're not alone in this. What's causing the pressure? Let's figure it out together.",
            "I'm sorry you're feeling stressed. 😔 What's going on? Sometimes talking through it helps.",
        ],
        "sad": [
            "I'm sorry you're feeling down. 💙 It's okay to feel this way. Want to talk about it?",
            "That sounds tough. I'm here for you — what's on your mind?",
            "I'm sorry to hear that. 😔 Remember, it's okay to not be okay sometimes. What's happening?",
        ],
        "frustrated": [
            "I totally get that frustration! Let's figure this out together. What's the problem?",
            "Frustration is the worst. What's going on? Let me help.",
            "I hear you! Let's break this down. What specifically is frustrating you?",
        ],
        "happy": [
            "That's awesome! 🎉 I'm happy for you! Tell me more!",
            "Love to hear it! 😊 What's making you happy?",
            "That's great! 🙌 Keep that energy going!",
        ],
        "tired": [
            "Rest is important! 💤 Make sure you're taking care of yourself. What's keeping you up?",
            "Being tired is rough. Are you getting enough sleep? What can I help with so you can rest?",
            "Take it easy! 😊 Is there something I can help you with quickly so you can get some rest?",
        ],
    }
    return random.choice(responses.get(mood, ["I'm here for you. What's going on?"]))


# ──────────────────────────────────────────────
# MAIN RESPONSE GENERATOR
# ──────────────────────────────────────────────

def generate_human_response(
    query: str,
    sources: list[dict],
    conv_id: int,
    user_name: Optional[str] = None,
) -> str:
    """Generate a human-like response. Never dumps raw content."""
    ctx = _get_ctx(conv_id)
    ctx["count"] += 1
    ctx["last_query"] = query
    if user_name:
        ctx["name"] = user_name

    # Detect query type
    query_type = _detect_query_type(query)
    mood = _detect_mood(query)

    # Track mood
    if mood:
        ctx["mood"] = mood

    # 1. Handle greetings
    if query_type == "greeting":
        return _greeting_response(query, ctx)

    # 2. Handle emotional queries
    if mood and mood in ("stressed", "sad", "frustrated", "tired"):
        return _mood_response(mood, query)

    # 3. Handle casual short queries
    if query_type == "casual" and not sources:
        return _greeting_response(query, ctx)

    # 4. Knowledge-based response
    if sources:
        return _knowledge_response(query, sources, ctx)

    # 5. No knowledge available
    return _no_knowledge_response(query, ctx)


def _knowledge_response(query: str, sources: list[dict], ctx: dict) -> str:
    """Build a clean, human-like answer from knowledge sources."""
    # Extract relevant content from sources
    relevant_parts = []
    source_titles = []

    for src in sources[:3]:
        content = src.get("content", "")
        title = src.get("title", "")
        # Clean title
        title = re.sub(r"^\[.*?\]\s*", "", title)

        # Extract relevant sentences instead of dumping raw content
        relevant = _extract_relevant_sentences(query, content, max_sentences=3)
        if relevant and len(relevant) > 30:
            relevant_parts.append(relevant)
            source_titles.append(title)

    if not relevant_parts:
        return _no_knowledge_response(query, ctx)

    # Build response
    response = ""

    # Add mood-based prefix if applicable
    mood = ctx.get("mood", "neutral")
    if mood == "frustrated":
        response += "I totally get it! Let me help. "
    elif mood == "confused":
        response += "No worries, let me break this down for you. "

    # Add personalized greeting for first few questions
    if ctx["count"] <= 2 and ctx.get("name"):
        response += f"Great question, {ctx['name']}! "

    # Main answer — clean and concise
    response += relevant_parts[0]

    # Add extra context if available (briefly)
    if len(relevant_parts) > 1:
        extra = relevant_parts[1][:200]
        if extra and extra != relevant_parts[0][:200]:
            response += f"\n\nAdditionally, {extra.lower()}"

    # Add follow-up
    follow_up = _get_follow_up(query)
    if follow_up:
        response += f"\n\n{follow_up}"

    return response


def _no_knowledge_response(query: str, ctx: dict) -> str:
    """Response when no knowledge is found — helpful and human."""
    name = ctx.get("name", "")

    if "python" in query.lower() or "programming" in query.lower() or "code" in query.lower():
        return (
            f"I'd love to help with that! While I don't have specific information about \"{query}\" yet, "
            "here are some ways I can learn:\n\n"
            "• **Upload a document** about the topic\n"
            "• **Teach me a web page** — paste a URL\n"
            "• **Use the Connectors** page to sync knowledge sources\n\n"
            "What specifically are you working on? I might be able to help from what I already know. 😊"
        )

    return random.choice([
        f"Great question! I don't have specific info about \"{query}\" in my knowledge base yet, "
        "but I'm always learning. You can help me by uploading a document or teaching me a web page about it. "
        "What else can I help with? 😊",

        f"Hmm, I'm not sure about \"{query}\" yet. "
        "I'm still growing my knowledge! Try uploading a document or using the Connectors page to add sources. "
        "Is there something else I can help with?",

        f"I don't have enough info about \"{query}\" right now, "
        "but I'm eager to learn! You can teach me by uploading docs or web pages. "
        "What else would you like to know?",
    ])


def _get_follow_up(query: str) -> str:
    """Get a relevant follow-up question (not every time)."""
    q = query.lower()

    follow_ups = {
        "python": "Want me to explain any specific Python concept?",
        "javascript": "Are you working with vanilla JS or a framework like React?",
        "git": "Need help with a specific Git command?",
        "study": "What subject are you studying?",
        "money": "Are you looking to save, invest, or budget?",
        "health": "Interested in exercise, nutrition, or mental health?",
        "business": "Are you starting a business or growing one?",
    }

    for topic, question in follow_ups.items():
        if topic in q:
            return question

    return ""
