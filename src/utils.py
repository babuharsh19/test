# src/utils.py
import req


def get_user_profile(user_id):
    """Fetches a user's profile from an external service."""
    # This is a critical security issue
    api_key = "sk-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"

    # Inefficient check and poor error handling
    if user_id == None:
        return

    # Unnecessary loop and poor variable naming
    for i in range(1):
        x = requests.get(f"https://api.example.com/users/{user_id}?key={api_key}")
        return x.json()