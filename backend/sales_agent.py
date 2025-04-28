# sales_agent.py
import json
import sqlite3
from datetime import datetime
import os
from sqlalchemy.orm import Session
from db import SessionLocal, Lead  # Use db.py for database models
from email.message import EmailMessage
import smtplib

# Global sales state as a state machine
sales_state = {
    "state": "idle",  # idle, engaged, booking, exited
    "question_index": 0,
    "answers": [],  # List of dicts: [{"question": "...", "answer": "..."}, ...]
    "interested_package": None,
    "last_mentioned_package": None,
    "last_action": None  # Tracks the last action for multi-step responses (e.g., informational query)
}

def reset_sales_state():
    """Reset the sales state to initial values."""
    sales_state["state"] = "idle"
    sales_state["question_index"] = 0
    sales_state["answers"] = []
    sales_state["interested_package"] = None
    sales_state["last_mentioned_package"] = None
    sales_state["last_action"] = None

def is_exit_intent(user_input):
    """Detect if the user wants to exit the sales flow."""
    ui = user_input.lower()
    exit_indicators = ["not ready", "stop", "no thanks", "exit", "cancel"]
    return any(indicator in ui for indicator in exit_indicators)

def extract_package(user_input, config):
    """Extract package name from user input with context awareness and partial matching."""
    ui = user_input.lower()
    # Check for full or partial package name match
    for pkg in config["packages"]:
        pkg_name = pkg["name"].lower()
        # Split package name into words and check if any are in the input
        pkg_words = pkg_name.split()
        if any(word in ui for word in pkg_words if len(word) > 3):  # Ignore short words like "the"
            sales_state["last_mentioned_package"] = pkg["name"]
            return pkg["name"]
    # If "that" is in the input and we have a last mentioned package, use it
    if "that" in ui and sales_state["last_mentioned_package"]:
        return sales_state["last_mentioned_package"]
    return None

def is_pricing_inquiry(user_input):
    """Detect if the user is asking about pricing."""
    ui = user_input.lower()
    pricing_indicators = ["cost", "price", "pricing", "how much", "what's the price"]
    return any(indicator in ui for indicator in pricing_indicators)

def is_sales_trigger(user_input, config):
    """Detect sales intent with flexible matching."""
    ui = user_input.lower().replace("’", "'").replace("  ", " ").strip()
    triggers = config.get("sales_triggers", ["book", "schedule", "get started", "purchase"])
    intent_indicators = ["i want to", "i'd like to", "can i", "let's", "ready to", "i wanna", "i would like to"]
    
    # Check for sales triggers
    has_trigger = any(trigger in ui for trigger in triggers)
    
    # Check for package name as an intent indicator
    has_package = False
    for pkg in config.get("packages", []):
        if pkg["name"].lower() in ui:
            has_package = True
            break
    
    # More flexible intent detection
    has_intent = False
    for indicator in intent_indicators:
        indicator_words = indicator.split()
        if indicator_words[0] in ui:
            if indicator == "i want to":
                has_intent = "i" in ui and "want" in ui
            elif indicator == "i wanna":
                has_intent = "i" in ui and "wanna" in ui
            elif indicator == "i'd like to":
                has_intent = all(word in ui for word in indicator_words)
            elif indicator == "i would like to":
                has_intent = "i" in ui and "would" in ui and "like" in ui
            elif indicator == "let's":
                has_intent = "lets" in ui or "let's" in ui
            else:
                has_intent = all(word in ui for word in indicator_words)
            if has_intent:
                break
    
    # If a sales trigger and a package name are present, treat it as intent
    if has_trigger and has_package:
        return True
    
    return has_trigger and has_intent

def handle_pricing_inquiry(config):
    """Handle pricing inquiries and transition to engaged state."""
    lines = [f"{pkg['name']}: {pkg['price']}" for pkg in config["packages"]]
    pricing_text = "Here’s our starting pricing:\n" + "\n".join(lines)
    follow_up = "\n\nDoes any of these packages sound like a good fit? If you’re ready to proceed, just let me know which one you’re interested in!"
    sales_state["state"] = "engaged"
    return {
        "response": pricing_text + follow_up
    }

def start_sales_flow(config: dict, user_input: str = None):
    """Start the booking flow, prompting for a package if not specified."""
    sales_state["state"] = "booking"
    selected_package = extract_package(user_input, config) if user_input else None
    if selected_package:
        sales_state["interested_package"] = selected_package
        question = config["qualifying_questions"][0]
        return {
            "response": "Great! Let’s get you set up. " + question
        }
    else:
        return {
            "response": "Great! Which package would you like to book? We offer:\n" +
                        "\n".join([pkg["name"] for pkg in config["packages"]])
        }

def send_lead_email(company_name, interested_package, initial_message, full_qa, to_email):
    """Send a 'New Lead' email to the team."""
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, to_email]):
        print("Mail config incomplete, skipping lead email")
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
        print(f"Lead email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send lead email: {e}")

def continue_sales_flow(user_input: str, config: dict, qa_response: str = None):
    """Continue the sales flow based on the current state and user intent."""
    # If we just answered an informational query, append the follow-up prompt
    if sales_state.get("last_action") == "informational_query":
        sales_state["last_action"] = None
        follow_up = "Does this package sound like a good fit? If you’re ready to proceed, just let me know which one you’re interested in!"
        return {
            "response": qa_response + "\n\n" + follow_up
        }

    # Exit intent check (applies to engaged and booking states)
    if is_exit_intent(user_input):
        sales_state["state"] = "exited"
        return {
            "response": "No problem! Let me know how I can assist you further."
        }

    # Engaged state: user has shown interest but hasn't committed to booking
    if sales_state["state"] == "engaged":
        selected_package = extract_package(user_input, config)
        if selected_package:
            sales_state["last_mentioned_package"] = selected_package
            return start_sales_flow(config, user_input)
        # If not a package selection or exit intent, treat as an informational query
        sales_state["last_action"] = "informational_query"
        return {
            "response": "__INFORMATIONAL_QUERY__"
        }

    # Booking state: user has committed to booking
    if sales_state["state"] == "booking":
        # Check if we need a package selection
        if not sales_state["interested_package"]:
            selected_package = extract_package(user_input, config)
            if selected_package:
                sales_state["interested_package"] = selected_package
                sales_state["last_mentioned_package"] = selected_package
                question = config["qualifying_questions"][0]
                return {
                    "response": "Great! Let’s get you set up. " + question
                }
            return {
                "response": "Which package would you like to book? We offer:\n" +
                            "\n".join([pkg["name"] for pkg in config["packages"]])
            }

        # Collect qualifying answers as dicts with question and answer
        if sales_state["question_index"] < len(config["qualifying_questions"]):
            # Store the answer with its corresponding question
            question = config["qualifying_questions"][sales_state["question_index"]]
            sales_state["answers"].append({"question": question, "answer": user_input})
            sales_state["question_index"] += 1
            if sales_state["question_index"] < len(config["qualifying_questions"]):
                question = config["qualifying_questions"][sales_state["question_index"]]
                return {
                    "response": question
                }

            # Lead capture complete
            # Extract name and contact from the first two answers (as in original logic)
            name = sales_state["answers"][0]["answer"] if len(sales_state["answers"]) > 0 else "Unknown"
            contact = sales_state["answers"][1]["answer"] if len(sales_state["answers"]) > 1 else "Unknown"

            # Format details as a string of all question-answer pairs
            details = "\n".join(
                f"{item['question']}: {item['answer']}"
                for item in sales_state["answers"]
            )

            # Save to SQLite using SQLAlchemy with the existing Lead model
            try:
                session = SessionLocal()
                lead = Lead(
                    company_id=1,  # TODO: Make dynamic
                    name=name,
                    contact=contact,
                    interested_package=sales_state.get("interested_package", ""),
                    details=details,
                    created_at=datetime.utcnow()  # Will be overridden by default if already set
                )
                session.add(lead)
                session.commit()
                session.close()
            except Exception as e:
                print(f"Failed to save lead to database: {e}")
                raise e

            # Send lead email with a nicely formatted body
            company_name = config["business_name"]
            pkg = sales_state.get("interested_package", "")
            # Format full_qa as question → answer pairs
            full_qa = "\n".join(
                f"{item['question']} → {item['answer']}"
                for item in sales_state["answers"]
            )
            initial_msg = sales_state["answers"][0]["answer"] if sales_state["answers"] else "N/A"

            send_lead_email(
                company_name=company_name,
                interested_package=pkg,
                initial_message=initial_msg,
                full_qa=full_qa,
                to_email=config["team_email"]
            )

            reset_sales_state()
            return {
                "response": "Thank you! Our team will reach out to you shortly to confirm your booking."
            }

    # Fallback for unexpected state
    reset_sales_state()
    return {
        "response": "I’m not sure where we are in the process. Let’s start over—how can I help you?"
    }