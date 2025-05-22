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

# MongoDB Collections
admin_users_collection = db['admin_users']
clients_collection = db['clients']
leads_collection = db['leads']

# ───────────────────────────────────────────────────────────────
# 1) State & Reset
# ───────────────────────────────────────────────────────────────
sales_state = {
    "state": "idle",          # idle, engaged, booking
    "question_index": 0,
    "answers": [],            # List[{"question": str, "answer": str}]
    "interested_package": None,
    "last_action": None       # For redirecting after informational query
}

def reset_sales_state():
    sales_state.update({
        "state": "idle",
        "question_index": 0,
        "answers": [],
        "interested_package": None,
        "last_action": None
    })

# ───────────────────────────────────────────────────────────────
# 2) Intent Detection
# ───────────────────────────────────────────────────────────────
# Questions get routed to QA even mid-flow if in "engaged"
QUESTION_RE = re.compile(r"\b(what|which|how|why|where|when|who)\b|\?$", re.IGNORECASE)

def is_question(text: str) -> bool:
    return bool(QUESTION_RE.search(text.strip()))

def is_exit_intent(text: str) -> bool:
    ui = text.lower()
    return any(k in ui for k in ["cancel", "never mind", "no thanks", "stop"])

def extract_package(text: str, config: dict) -> str | None:
    ui = text.lower()
    # Match any package name word > 3 chars
    for pkg in config.get("packages", []):
        name = pkg["name"]
        words = [w for w in name.lower().split() if len(w) > 3]
        if any(w in ui for w in words):
            sales_state["last_mentioned_package"] = name
            return name
    # Fallback: "that, this, it" refers to last mentioned
    pronouns = ["that", "it", "this"]
    if any(p in ui.split() for p in pronouns) and sales_state.get("last_mentioned_package"):
        return sales_state["last_mentioned_package"]
    return None

def is_pricing_inquiry(text: str) -> bool:
    ui = text.lower()
    return any(k in ui for k in ["cost", "price", "pricing", "how much"])

def is_sales_trigger(text: str, config: dict) -> bool:
    ui = text.lower()
    # Configured triggers + generic terms
    triggers = config.get("sales_triggers", []) + ["book", "purchase", "schedule", "get started"]
    # Word-boundary match for generic booking terms
    if re.search(r"\b(book|purchase)\b", ui):
        return True
    # Substring match for configured triggers
    return any(trig.lower() in ui for trig in triggers)

# ───────────────────────────────────────────────────────────────
# 3) Email Helper
# ───────────────────────────────────────────────────────────────
def send_lead_email(company_name, interested_package, initial_message, full_qa, to_email):
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT   = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER   = os.getenv("SMTP_USER")
    SMTP_PASS   = os.getenv("SMTP_PASS")
    FROM_EMAIL  = os.getenv("FROM_EMAIL", SMTP_USER)

    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and to_email):
        print("⚠️ Mail config incomplete, skipping email")
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
        print(f"✅ Lead email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send lead email: {e}")

# ───────────────────────────────────────────────────────────────
# 4) Handlers
# ───────────────────────────────────────────────────────────────
def handle_pricing_inquiry(config: dict) -> dict:
    """Show pricing and move to 'engaged'."""
    lines = [f"{p['name']}: {p['price']}" for p in config.get("packages", [])]
    text  = "Here’s our starting pricing:\n" + "\n".join(lines)
    text += "\n\nDoes one of these sound good? If so, let me know!"
    sales_state["state"] = "engaged"
    return {"response": text}

def start_sales_flow(config: dict, user_input: str | None = None) -> dict:
    """Begin booking or prompt package choice."""
    sales_state["state"] = "booking"
    pkg = extract_package(user_input or "", config)

    if not pkg and sales_state.get("last_mentioned_package"):
        pkg = sales_state["last_mentioned_package"]

    if pkg:
        sales_state["interested_package"] = pkg
        ques = config["qualifying_questions"][0]
        return {"response": f"Great! You chose **{pkg}**. {ques}"}

    options = "\n".join(p["name"] for p in config.get("packages", []))
    return {"response": "Which package would you like? We offer:\n" + options}

def continue_sales_flow(user_input: str, config: dict, qa_response: str = None) -> dict:
    """
    - If 'engaged' and qa_response present, tack on a booking prompt.
    - If 'booking', walk through qualifiers + contact, then persist + email.
    """
    # 1) If we just answered an informational QA, follow up
    if sales_state["state"] == "engaged" and qa_response:
        prompt = "If you’re ready to book, just let me know which package!"
        return {"response": qa_response + "\n\n" + prompt}

    # 2) Exit flow if requested
    if is_exit_intent(user_input):
        reset_sales_state()
        return {"response": "No problem—happy to help with anything else."}

    # 3) Engaged state: look for booking intent
    if sales_state["state"] == "engaged":
        pkg = extract_package(user_input, config)
        if pkg and is_sales_trigger(user_input, config):
            return start_sales_flow(config, user_input)
        # treat everything else as QA
        sales_state["last_action"] = "informational_query"
        return {"response": "__INFORMATIONAL_QUERY__"}

    # 4) Booking state: collect qualifiers
    if sales_state["state"] == "booking":
        idx = sales_state["question_index"]
        questions = config["qualifying_questions"] + [
            "What’s your name?", "Best phone or email to reach you?"
        ]

        # record answer
        sales_state["answers"].append({
            "question": questions[idx],
            "answer":   user_input
        })
        idx += 1

        # still more questions?
        if idx < len(questions):
            sales_state["question_index"] = idx
            return {"response": questions[idx]}

        # done: persist and email
        info = sales_state["answers"]
        name    = info[-2]["answer"]
        contact = info[-1]["answer"]
        qualifiers = info[:-2]

        # Save to MongoDB
        lead_data = {
            "client_id": 1,  # Replace with dynamic lookup if needed
            "name": name,
            "email": contact,
            "responses": {"interested_package": sales_state["interested_package"], "qualifiers": qualifiers},
            "created_at": datetime.utcnow()
        }

        # Insert into leads collection
        leads_collection.insert_one(lead_data)

        full_qa = "\n\n".join(f"{q['question']} → {q['answer']}" for q in info)
        initial = info[0]["answer"]

        send_lead_email(
            company_name=config["business_name"],
            interested_package=sales_state.get("interested_package"),
            initial_message=initial,
            full_qa=full_qa,
            to_email=config.get("team_email", "")
        )

        reset_sales_state()
        return {"response": "Thanks! Our team will reach out shortly to finalize your booking."}

    # 5) Idle fallback
    reset_sales_state()
    return {"response": "How can I assist you today?"}
