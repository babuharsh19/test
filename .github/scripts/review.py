# .github/scripts/review.py

import os
import requests
import json

# --- Configuration ---
# Get environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
PR_URL = os.environ.get("PR_URL")

# Gemini API endpoint
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"


# --- Helper Functions ---

def get_pr_diff():
    """Fetches the diff of the pull request from GitHub."""
    if not PR_URL:
        print("Error: PR_URL environment variable not set.")
        return None

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3.diff'
    }
    try:
        response = requests.get(PR_URL, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR diff: {e}")
        return None


def get_review_from_gemini(diff):
    """Sends the diff to Gemini API and gets a review."""
    if not diff:
        print("No diff content to review.")
        return None

    # You can customize this prompt to fit your team's standards
    prompt = f"""
    Please act as an expert code reviewer. Review the following code changes (in diff format) and provide feedback.
    Focus on:
    1.  Potential bugs or logic errors.
    2.  Performance issues.
    3.  Adherence to best practices.
    4.  Code readability and maintainability.
    5.  Security vulnerabilities.

    Provide your feedback in Markdown format. If there are no issues, simply say "Looks good to me!".

    Here is the diff:
    ```diff
    {diff}
    ```
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        print(f"Response body: {response.text}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Full response: {result}")
        return None


def post_comment_to_pr(comment):
    """Posts a comment to the GitHub pull request."""
    if not comment:
        print("No comment to post.")
        return

    comments_url = f"{PR_URL}/comments"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {'body': comment}

    try:
        response = requests.post(comments_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("Successfully posted comment to PR.")
    except requests.exceptions.RequestException as e:
        print(f"Error posting comment to PR: {e}")
        print(f"Response body: {response.text}")


# --- Main Execution ---

if __name__ == "__main__":
    print("Starting Gemini Code Review...")
    pr_diff = get_pr_diff()

    if pr_diff:
        # Be mindful of token limits. For very large PRs, you might need to truncate the diff.
        if len(pr_diff) > 30000:  # Gemini Pro has a 32k token limit, be safe
            print("PR diff is too large. Truncating.")
            pr_diff = pr_diff[:30000]

        review = get_review_from_gemini(pr_diff)
        if review:
            post_comment_to_pr(review)
    else:
        print("Could not retrieve PR diff. Exiting.")

    print("Review process finished.")