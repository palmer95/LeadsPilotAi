# list_leads.py

from db import SessionLocal, Lead, AdminUser

def main():
    session = SessionLocal()
    leads = session.query(Lead).order_by(Lead.created_at.desc()).all()
    admins = session.query(AdminUser).order_by(AdminUser.created_at.desc()).all()
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
    
    for a in admins:
        print(
            f"ID: {a.id}\n"
            f"Email: {a.email}\n"
            f"Token: {a.invite_token}\n"
            f"Pass: {a.password_hash}\n"
            f"Role: {a.role}\n"
            + "-"*40
        )
    
    session.close()

if __name__ == "__main__":
    main()
