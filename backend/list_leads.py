# list_leads.py

from db import SessionLocal, Lead

def main():
    session = SessionLocal()
    leads = session.query(Lead).order_by(Lead.created_at.desc()).all()
    for l in leads:
        print(
            f"ID: {l.id}\n"
            f"Company: {l.company_id}\n"
            f"Name: {l.name}\n"
            f"Contact: {l.contact}\n"
            f"Package: {l.interested_package}\n"
            f"Details:\n{l.details}\n"
            f"Created: {l.created_at}\n"
            + "-"*40
        )
    session.close()

if __name__ == "__main__":
    main()
