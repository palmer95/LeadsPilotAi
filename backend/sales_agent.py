# sales_agent.py
from db import SessionLocal, Lead
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime


PRICING_TRIGGERS = ["how much", "pricing", "cost", "what’s the price"]

def send_lead_email(company_name, interested_package, initial_message, full_qa, to_email):
    #
    # Sends a “New Lead” email to the team.
    # Expects these environment vars to be set:
    #   SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, TEAM_EMAIL

    # Load mail settings from env
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT   = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER   = os.getenv("SMTP_USER")
    SMTP_PASS   = os.getenv("SMTP_PASS")
    FROM_EMAIL  = os.getenv("FROM_EMAIL", SMTP_USER)

    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, to_email]):
        # missing config, fail silently or log
        print("⚠️ Mail config incomplete, skipping lead email")
        return

    # Build the email
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

    # Send via SMTP SSL
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print("❌ Failed to send lead email:", e)

def is_pricing_inquiry(user_input):
    ui = user_input.lower()
    return any(trigger in ui for trigger in PRICING_TRIGGERS)

def handle_pricing_inquiry(config):
    # Build the pricing list
    lines = [f"{pkg['name']}: {pkg['price']}" for pkg in config["packages"]]
    pricing_text = "Here’s our starting pricing:\n" + "\n".join(lines)

    follow_up = (
        "\n\nDo any of these packages sound like a good fit?\n"
        "If so, just let me know which one you're interested in and I’ll walk you through booking."
    )

    # Now start the sales flow
    first_q = config["qualifying_questions"][0]
    # mark sales state active
    sales_state["active"] = True
    sales_state["question_index"] = 0
    sales_state["answers"] = []
    return {
        "response":pricing_text + follow_up
    }

def extract_package(user_input, config):
    ui = user_input.lower()
    for pkg in config["packages"]:
        if pkg["name"].lower() in ui:
            return pkg["name"]
    return None

sales_state = {
    "active": False,
    "question_index": 0,
    "answers": []
}

def is_sales_trigger(user_input, config):
    user_input = user_input.lower()
    return any(trigger in user_input for trigger in config["sales_triggers"])

def start_sales_flow(config, user_input=""):
    sales_state["active"] = True
    sales_state["question_index"] = 0
    sales_state["answers"] = []

    selected_package = extract_package(user_input, config)
    sales_state["interested_package"] = selected_package or ""

    first_question = config["qualifying_questions"][0]
    return {
        "response": f"Great! Let's get you set up. {first_question}"
    }

def continue_sales_flow(user_input, config):
    sales_state["answers"].append(user_input)
    sales_state["question_index"] += 1

        # Extend total questions: core + contact
    total_questions = config["qualifying_questions"] + [
        "What’s your name?",
        "What’s the best phone number or email to reach you?"
    ]

    if sales_state["question_index"] < len(total_questions):
        next_q = total_questions[sales_state["question_index"]]
        return { "response": next_q }
    else:
        # Last two answers:
        name = sales_state["answers"][-2]
        contact = sales_state["answers"][-1]

        # All earlier answers (qualifying questions):
        details = sales_state["answers"][:-2]

        # Write to SqlLite
        session = SessionLocal()
        lead = Lead(
            company_id=1,  # hardcoded or dynamic in future
            name=name,
            contact=contact,
            interested_package=sales_state.get("interested_package", ""),
            details="\n".join([
                f"{q}: {a}" for q, a in zip(
                    config["qualifying_questions"], details
                )
            ])
        )
        session.add(lead)
        session.commit()
        session.close()

        # Email
        company_name = config["business_name"]
        pkg = sales_state.get("interested_package", "")
        # Build a flattened summary of Q&A
        qa_lines = "\n".join(
            f"{qa['question']}\n→ {qa['answer']}"
            for qa in sales_state["answers"]
        )
        initial_msg = sales_state["answers"][0]["answer"]

        # Send to the team
        send_lead_email(
            company_name=company_name,
            interested_package=pkg,
            initial_message=initial_msg,
            full_qa=qa_lines,
            to_email=config["team_email"]
        )


        reset_sales_state()

        #print("\n===== NEW LEAD CAPTURED =====")
        #print(summary)
        #print("=================================\n")

        return {
            "response": f"Thanks! I’ve passed your info to the team. We’ll reach out shortly."
        }

def is_active():
    return sales_state["active"]

def reset_sales_state():
    sales_state["active"] = False
    sales_state["question_index"] = 0
    sales_state["answers"] = []
