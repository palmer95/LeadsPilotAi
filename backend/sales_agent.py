# sales_agent.py
from db import SessionLocal, Lead



PRICING_TRIGGERS = ["how much", "pricing", "cost", "what’s the price"]

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
