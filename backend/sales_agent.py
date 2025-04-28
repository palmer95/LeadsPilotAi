# sales_agent.py
from db import SessionLocal, Lead
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sales_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PRICING_TRIGGERS = ["how much", "pricing", "cost", "what’s the price"]
EXIT_INTENTS = ["not ready", "not sure", "maybe later", "stop", "exit", "cancel"]

def send_lead_email(company_name, interested_package, initial_message, full_qa, to_email):
    """Send a 'New Lead' email to the team."""
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, to_email]):
        logger.warning("Mail config incomplete, skipping lead email")
        return

    msg = EmailMessage()
    msg["Subject"] = f"New lead for {company_name}"
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    body = f"""
New lead for {company_name}
Time (UTC): {datetime.utcnow().isoformat()}

Interested package: {interested_package or 'N/A'}
Initial message: {initial_message or 'N/A'}

All answers:
{full_qa}
"""
    msg.set_content(body.strip())

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        logger.info(f"Lead email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send lead email: {e}")

def is_pricing_inquiry(user_input):
    """Detect pricing-related queries."""
    ui = user_input.lower()
    return any(trigger in ui for trigger in PRICING_TRIGGERS)

def handle_pricing_inquiry(config):
    """Handle pricing inquiries and initiate sales flow with confirmation."""
    lines = [f"{pkg['name']}: {pkg['price']}" for pkg in config["packages"]]
    pricing_text = "Here’s our starting pricing:\n" + "\n".join(lines)

    follow_up = (
        "\n\nDoes any of these packages sound like a good fit? "
        "If you’re ready to proceed, just let me know which one you’re interested in!"
    )
    sales_state["pending"] = True
    sales_state["interested_package"] = None
    # Clear last mentioned package on pricing inquiry
    sales_state["last_mentioned_package"] = None

    return {
        "response": pricing_text + follow_up
    }

def extract_package(user_input, config):
    """Extract package name from user input with context awareness."""
    ui = user_input.lower()
    # Check for explicit package name
    for pkg in config["packages"]:
        if pkg["name"].lower() in ui:
            sales_state["last_mentioned_package"] = pkg["name"]
            return pkg["name"]
    # If "that" is in the input and we have a last mentioned package, use it
    if "that" in ui and sales_state["last_mentioned_package"]:
        return sales_state["last_mentioned_package"]
    return None

def is_exit_intent(user_input):
    """Detect if the user wants to exit the sales flow."""
    ui = user_input.lower()
    return any(intent in ui for intent in EXIT_INTENTS)

def is_sales_trigger(user_input, config):
    """Detect sales intent with more flexible matching."""
    # Normalize input: lowercase, replace apostrophes, and normalize spaces
    ui = user_input.lower().replace("’", "'").replace("  ", " ").strip()
    # Use config sales_triggers if available, otherwise fall back to defaults
    triggers = config.get("sales_triggers", ["book", "schedule", "get started", "purchase"])
    intent_indicators = ["i want to", "i'd like to", "can i", "let's", "ready to"]
    
    # Check for sales triggers
    has_trigger = any(trigger in ui for trigger in triggers)
    
    # More flexible intent detection: check for partial matches of intent phrases
    has_intent = False
    for indicator in intent_indicators:
        indicator_words = indicator.split()
        # Require at least the first word of the intent phrase to match, and allow flexibility
        if indicator_words[0] in ui:
            # For "i want to", ensure at least "i" and "want" are present
            if indicator == "i want to":
                has_intent = "i" in ui and "want" in ui
            # For "let's", accept "lets" as a match
            elif indicator == "let's":
                has_intent = "lets" in ui or "let's" in ui
            # For others, require all words but allow flexibility in order
            else:
                has_intent = all(word in ui for word in indicator_words)
            if has_intent:
                break
    
    return has_trigger and has_intent

sales_state = {
    "active": False,
    "pending": False,
    "question_index": 0,
    "answers": [],
    "interested_package": None,
    "last_mentioned_package": None
}

def start_sales_flow(config, user_input=""):
    """Start the sales flow after confirmation."""
    selected_package = extract_package(user_input, config)
    sales_state["interested_package"] = selected_package or ""
    sales_state["active"] = True
    sales_state["pending"] = False
    sales_state["question_index"] = 0
    sales_state["answers"] = []

    first_question = config["qualifying_questions"][0]
    return {
        "response": f"Great! Let’s get you set up. {first_question}"
    }

def continue_sales_flow(user_input: str, config: dict):
    """Continue the sales flow, handling user responses dynamically."""
    # If in pending state (after pricing inquiry), confirm intent
    if sales_state["pending"]:
        selected_package = extract_package(user_input, config)
        if selected_package:
            sales_state["last_mentioned_package"] = selected_package
            return start_sales_flow(config, user_input)
        if is_exit_intent(user_input):
            reset_sales_state()
            return {
                "response": "No problem! Let me know how I can assist you further."
            }
        return {
            "response": "Which package would you like to proceed with? Or let me know if you’re not ready yet."
        }

    # Record the user's answer
    idx = sales_state["question_index"]
    total_questions = config["qualifying_questions"] + [
        "What’s your name?",
        "What’s the best phone number or email to reach you?"
    ]

    # Handle dynamic responses (e.g., user hesitancy)
    hesitant_phrases = ["not sure", "maybe", "i don’t know"]
    if any(phrase in user_input.lower() for phrase in hesitant_phrases):
        return {
            "response": (
                "That’s okay! Let’s take a step back. "
                f"Would you like to know more about {total_questions[idx]} "
                "or explore something else?"
            )
        }

    sales_state["answers"].append({
        "question": total_questions[idx],
        "answer": user_input
    })
    sales_state["question_index"] = idx + 1

    # Continue with next question or finish
    if sales_state["question_index"] < len(total_questions):
        next_q = total_questions[sales_state["question_index"]]
        return {"response": next_q}

    # All questions answered, save lead
    name = sales_state["answers"][-2]["answer"]
    contact = sales_state["answers"][-1]["answer"]
    qualifiers = sales_state["answers"][:-2]

    # Save to SQLite
    try:
        session = SessionLocal()
        lead = Lead(
            company_id=1,  # TODO: Make dynamic
            name=name,
            contact=contact,
            interested_package=sales_state.get("interested_package", ""),
            details="\n".join(
                f"{config['qualifying_questions'][i]}: {qualifiers[i]['answer']}"
                for i in range(len(config['qualifying_questions']))
            )
        )
        session.add(lead)
        session.commit()
        session.close()
        logger.info(f"Lead saved for {config['business_name']}: {name}")
    except Exception as e:
        logger.error(f"Failed to save lead for {config['business_name']}: {e}")
        raise

    # Send lead email
    company_name = config["business_name"]
    pkg = sales_state.get("interested_package", "")
    qa_lines = "\n\n".join(
        f"{item['question']}\n→ {item['answer']}"
        for item in sales_state["answers"]
    )
    initial_msg = sales_state["answers"][0]["answer"]

    send_lead_email(
        company_name=company_name,
        interested_package=pkg,
        initial_message=initial_msg,
        full_qa=qa_lines,
        to_email=config["team_email"]
    )

    # Reset state
    reset_sales_state()

    return {
        "response": (
            "Thanks! I’ve passed your info to the team. "
            "We’ll reach out shortly."
        )
    }

def is_active():
    return sales_state["active"]

def reset_sales_state():
    sales_state["active"] = False
    sales_state["pending"] = False
    sales_state["question_index"] = 0
    sales_state["answers"] = []
    sales_state["interested_package"] = None