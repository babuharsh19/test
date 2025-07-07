# src/utils.py
import requests


def get_user_profile(user_id):
    """Fetches a user's profile from an external service."""
    if not user_id:
        return None

    try:
        response = requests.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Could not fetch user profile: {e}")
        return None