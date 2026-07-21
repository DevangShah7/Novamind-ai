"""One-shot cleanup: drop users whose email isn't a valid Pydantic EmailStr.

These rows were created by earlier smoke tests that used fake
`.local` / `@novamind.local` domains. Pydantic v2's `EmailStr`
validator rejects them on the response side, so the admin list
endpoint now 500s on serialization. Deleting these unblocks it.

Idempotent — safe to re-run.
"""
from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
try:
    bad = (
        db.query(User)
        .filter(
            (User.email.like("%.local"))
            | (User.email.like("%@novamind.local"))
        )
        .all()
    )
    if not bad:
        print("Nothing to clean up.")
    else:
        for u in bad:
            print(f"Deleting id={u.id} email={u.email}")
            db.delete(u)
        db.commit()
        print(f"Removed {len(bad)} bad rows.")
finally:
    db.close()
