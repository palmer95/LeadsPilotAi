# sales_agent.py

import re
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pymongo import MongoClient
import logging

# ───────────────────────────────────────────────────────────────
# MongoDB Setup
# ───────────────────────────────────────────────────────────────
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']
leads_collection = db['leads']

# ───────────────────────────────────────────────────────────────
# 1) State Management Functions
# ───────────────────────────────────────────────────────────────
def get_initial_state():
    """Returns a clean state dictionary for a new session."""
    return {
        "state": "idle",          # idle, engaged, booking
        "question_index": 0,
        "answers": [],
        "interested_package": None,
        "last_mentioned_package": None,
    }

def reset_sales_state():
    """Convenience function to get a fresh state."""
    return get_initial_state()

# ───────────────────────────────────────────────────────────────
# 2) Intent Detection (Functions now accept state where needed)
# ───────────────────────────────────────────────────────────────
QUESTION_RE = re.compile(r"\b(what|which|how|why|where|when|who)\b|\?$", re.IGNORECASE)

def is_question(text: str) -> bool:
    return bool(QUESTION_RE.search(text.strip()))

def is_exit_intent(text: str) -> bool:
    ui = text.lower()
    return any(k in ui for k in ["cancel", "never mind", "no thanks", "stop"])

def extract_package(text: str, config: dict, state: dict) -> str | None:
    ui = text.lower()
    for pkg in config.get("packages", []):
        name = pkg["name"]
        words = [w for w in name.lower().split() if len(w) > 3]
        if any(w in ui for w in words):
            # We don't modify state here, just return the name.
            # The calling function will decide whether to update last_mentioned_package.
            return name
            
    pronouns = ["that", "it", "this"]
    if any(p in ui.split() for p in pronouns) and state.get("last_mentioned_package"):
        return state["last_mentioned_package"]
    return None

def is_pricing_inquiry(text: str) -> bool:
    ui = text.lower()
    return any(k in ui for k in ["cost", "price", "pricing", "how much"])

def is_sales_trigger(text: str, config: dict) -> bool:
    ui = text.lower()
    triggers = config.get("sales_triggers", []) + ["book", "purchase", "schedule", "get started"]
    if re.search(r"\b(book|purchase)\b", ui):
        return True
    return any(trig.lower() in ui for trig in triggers)

# ───────────────────────────────────────────────────────────────
# 3) Email Helper (No changes needed)
# ───────────────────────────────────────────────────────────────
def send_lead_email(company_name, interested_package, initial_message, full_qa, to_email):
    # This function does not depend on state, so it remains unchanged.
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT   = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER   = os.getenv("SMTP_USER")
    SMTP_PASS   = os.getenv("SMTP_PASS")
    FROM_EMAIL  = os.getenv("FROM_EMAIL", SMTP_USER)

    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and to_email):
        logging.warning("Mail config incomplete, skipping email")
        return

    msg = EmailMessage()
    msg["Subject"] = f"New lead for {company_name}"
    msg["From"]    = FROM_EMAIL
    msg["To"]      = to_email

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
        logging.info(f"Lead email sent to {to_email}")
    except Exception as e:
        logging.error(f"Failed to send lead email: {e}")

# ───────────────────────────────────────────────────────────────
# 4) Handlers (Refactored to be stateless)
#    They now all return a tuple: (response_dictionary, new_state_dictionary)
# ───────────────────────────────────────────────────────────────
def handle_pricing_inquiry(config: dict, state: dict) -> tuple[dict, dict]:
    """Show pricing and move to 'engaged'."""
    lines = [f"{p['name']}: {p['price']}" for p in config.get("packages", [])]
    text  = "Here’s our starting pricing:\n" + "\n".join(lines)
    text += "\n\nDoes one of these sound good? If so, I can help you book a time."
    
    new_state = state.copy()
    new_state["state"] = "engaged"
    
    return {"response": text}, new_state

def start_sales_flow(config: dict, state: dict, user_input: str | None = None) -> tuple[dict, dict]:
    """Begin booking or prompt package choice."""
    new_state = state.copy()
    new_state["state"] = "booking"
    
    pkg = extract_package(user_input or "", config, new_state)

    if not pkg and new_state.get("last_mentioned_package"):
        pkg = new_state["last_mentioned_package"]

    if pkg:
        new_state["interested_package"] = pkg
        ques = config["qualifying_questions"][0]
        response = {"response": f"Great! To get started with the **{pkg}** package, I just have a few quick questions. First, {ques}"}
    else:
        options = "\n".join(p["name"] for p in config.get("packages", []))
        response = {"response": "Which package would you like to get started with? We offer:\n" + options}

    return response, new_state

def continue_sales_flow(user_input: str, config: dict, state: dict, qa_response: str = None) -> tuple[dict, dict]:
    """Main logic for continuing a conversation in a sales-related state."""
    new_state = state.copy() # Work with a copy to avoid side effects

    # 1) If we just answered an informational QA while engaged, follow up
    if new_state["state"] == "engaged" and qa_response:
        prompt = "If you’re ready to book, just let me know which package you're interested in!"
        return {"response": qa_response + "\n\n" + prompt}, new_state

    # 2) Exit flow if requested, at any point
    if is_exit_intent(user_input):
        return {"response": "No problem—happy to help with anything else."}, reset_sales_state()

    # 3) Engaged state: look for booking intent, otherwise treat as QA
    if new_state["state"] == "engaged":
        pkg = extract_package(user_input, config, new_state)
        if pkg:
             new_state['last_mentioned_package'] = pkg
        if pkg and is_sales_trigger(user_input, config):
            return start_sales_flow(config, new_state, user_input)
        
        # If no sales trigger, assume it's an informational question
        return {"response": "__INFORMATIONAL_QUERY__"}, new_state

    # 4) Booking state: walk through qualifiers + contact, then persist + email
    if new_state["state"] == "booking":
        idx = new_state["question_index"]
        questions = config["qualifying_questions"] + [
            "Perfect. And what is your full name?", "Thank you. Finally, what’s the best email address to reach you at?"
        ]

        # Record the previous answer
        # On the first question, the user's input might be the package name.
        if idx > 0:
            new_state["answers"].append({
                "question": questions[idx-1],
                "answer":   user_input
            })
        else: # Handle case where a package was just selected
            if not new_state['interested_package']:
                pkg = extract_package(user_input, config, new_state)
                new_state['interested_package'] = pkg
        
        # Still more questions? Ask the next one.
        if idx < len(questions):
            response = {"response": questions[idx]}
            new_state["question_index"] = idx + 1
            return response, new_state

        # --- Flow Complete: Persist and Finalize ---
        # Record the final answer (email)
        new_state["answers"].append({"question": questions[idx-1], "answer": user_input})

        # Extract lead details from the answers list
        info = new_state["answers"]
        name = info[-2]["answer"]
        contact_email = info[-1]["answer"]
        qualifiers = info[:-2]

        lead_data = {
            "company_slug": config.get("slug", "unknown"),
            "name": name,
            "email": contact_email,
            "interested_package": new_state["interested_package"],
            "qualifying_answers": qualifiers,
            "created_at": datetime.utcnow()
        }
        leads_collection.insert_one(lead_data)

        full_qa = "\n\n".join(f"{q['question']}\n→ {q['answer']}" for q in info)
        initial_message = qualifiers[0]['answer'] if qualifiers else "N/A"

        send_lead_email(
            company_name=config["business_name"],
            interested_package=new_state.get("interested_package"),
            initial_message=initial_message,
            full_qa=full_qa,
            to_email=config.get("team_email", "")
        )

        response = {"response": "Thanks! Our team will reach out shortly to finalize everything."}
        return response, reset_sales_state() # Reset state after completion

    # Fallback case (should not be reached if logic in app.py is correct)
    return {"response": "How can I help you today?"}, reset_sales_state()