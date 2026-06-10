def search_contacts(name: str) -> dict:
    """Search contacts by name."""
    return {"email": "alex@example.com"}

def read_inbox(limit: int = 10) -> list:
    """Read recent emails from inbox."""
    return []

def create_draft(to: str, subject: str, body: str) -> dict:
    """Create an email draft."""
    return {"draft_id": "draft_123"}

def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email."""
    return {"sent": True}
