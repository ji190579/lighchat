
from langchain_core.messages import HumanMessage, AIMessage
from src.services.faq_handler import FAQHandler
from src.core.config import load_config


config = load_config()
my_profile_name = config["my_profile_name"]
faq_handler = FAQHandler()

GREETING_KEYWORDS = ["hi", "hello", "hey", "good morning", "good evening", "thanks", "thank you", "appreciate"]
PRICE_KEYWORDS = ["how much", "price", "cost", "fees", "charges"]


def is_greeting_or_compliment(text):
    return any(word in text.lower() for word in GREETING_KEYWORDS) and len(text.split()) <= 6


def is_price_question(text):
    return any(word in text.lower() for word in PRICE_KEYWORDS)


def random_greeting_response(profile_name=my_profile_name):
    import random

    roles = [
        "Principal Software Engineer working in Banking System and currently lead the trade finance team uisng web java platform and recennty cerftified in AI program and working many projects in RAG using LLMs",
    ]

    openings = [
        "Hello",
        "Hi",
        "Welcome",
        "Good to see you",
        "Glad you're here"
    ]

    focus_areas = [
        "career background",
        "banking systems",
        "microservices architecture",
        "AI and RAG systems",
        "system modernization",
        "trade finance platforms"
    ]

    templates = [
        "{open}! I'm {name}, a {role}. How can I assist you today?",
        "{open}! {name} here — {role}. What would you like to discuss?",
        "{open}. I'm {name}, specialized in {role}. What can I help you with?",
        "{open}! You're speaking with {name}, {role}. Feel free to ask about {focus}.",
        "{open}! {name} here. I work in {role}. What would you like to explore?"
    ]

    return random.choice(templates).format(
        open=random.choice(openings),
        name=profile_name,
        role=random.choice(roles),
        focus=random.choice(focus_areas)
    )


def check_faq(user_message, threshold=0.65):
    """
    Check if user message matches FAQ database

    Args:
        user_message: User's question
        threshold: Minimum similarity score (0-1)

    Returns:
        dict with answer, score, matched_question, source
        Returns None if no match
    """
    result = faq_handler.find_answer(user_message, threshold=threshold)

    if result["answer"]:
        return {
            "answer": result["answer"],
            "score": result["score"],
            "matched_question": result["matched_question"],
            "source": "FAQ"
        }
    else:
        return None


def is_small_talk(msg):
    content = msg.content if hasattr(msg, 'content') else msg

    content_str = str(content).lower()

    small_talk_phrases = ["hello", "hi", "how are you", "thanks", "thank you"]
    return any(phrase in content_str for phrase in small_talk_phrases)


def compress_chat_history(chat_history, max_turns=5, max_length=300):
    processed_history = []

    trimmed = chat_history[-max_turns * 2:]

    for msg in trimmed:
        if is_small_talk(msg):
            continue

        content = msg.content if hasattr(msg, 'content') else msg

        if isinstance(content, list):
            if len(content) >= 2:
                processed_history.append(HumanMessage(content=str(content[0])[:max_length]))
                processed_history.append(AIMessage(content=str(content[1])[:max_length]))
            continue

        content_str = str(content)[:max_length]

        if isinstance(msg, HumanMessage) or (isinstance(msg, str) and len(processed_history) % 2 == 0):
            processed_history.append(HumanMessage(content=content_str))
        elif isinstance(msg, AIMessage) or (isinstance(msg, str) and len(processed_history) % 2 != 0):
            processed_history.append(AIMessage(content=content_str))
        else:
            processed_history.append(msg)

    return processed_history[-max_turns:]
