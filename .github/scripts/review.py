# .github/scripts/review.py

import os
import requests
import json
import subprocess
import re

# --- Configuration ---
# Get environment variables from the GitHub Actions workflow
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("PR_NUMBER")
COMMIT_ID = os.environ.get("COMMIT_ID")

# **FIXED** Gemini API endpoint with the correct model name
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"


# --- Helper Functions ---

def get_pr_diff():
    """
    Fetches the diff of the pull request using the git command,
    as it's more reliable within the Actions runner environment.
    """
    try:
        # Fetch the base branch of the pull request
        target_branch = os.environ.get('GITHUB_BASE_REF', 'main')
        subprocess.run(['git', 'fetch', 'origin', target_branch], check=True, capture_output=True)

        # Get the diff between the current commit and the target branch
        diff_command = ['git', 'diff', f'origin/{target_branch}...{COMMIT_ID}']
        result = subprocess.run(diff_command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e}")
        print(f"Stderr: {e.stderr}")
        return None


def get_review_from_gemini(diff):
    """
    Sends the diff to the Gemini API and asks for a review in a structured JSON format.
    """
    if not diff:
        print("No diff content to review.")
        return None

    # This prompt is engineered to request a JSON output.
    prompt = f"""
    Please act as an expert, meticulous code reviewer and a security analyst.
    Review the following code changes (in diff format) for a Python project.
    Your feedback should be strict and detailed.

    Analyze the following aspects:
    1.  **Security Vulnerabilities**: Hardcoded secrets, API keys, etc.
    2.  **Potential Bugs**: Logic errors, unhandled exceptions.
    3.  **Best Practices & PEP 8**: Shadowing built-ins, non-compliance with PEP 8.
    4.  **Readability & Maintainability**: Unclear names, typos.

    Provide your feedback as a JSON array of objects. Each object should represent a single comment and have the following structure:
    `{{
        "path": "<The full path to the file>",
        "line": <The line number in the new file where the issue is>,
        "comment": "<Your concise review comment for this specific line>"
    }}`

    - The 'line' number **must** correspond to a line that was added or modified in the diff.
    - If you find a hardcoded secret, flag it as a CRITICAL security issue in the comment.
    - If there are absolutely no issues, return an empty JSON array: `[]`.

    Here is the diff:
    ```diff
    {diff}
    ```
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {'Content-Type': 'application/json'}
    result_text = ""  # Initialize to ensure it's available in the except block

    try:
        response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result_text = response.json()['candidates'][0]['content']['parts'][0]['text']

        # **IMPROVED JSON PARSING**
        # Use regex to find the JSON array within the response text.
        # This is more robust than simple string stripping.
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            print("Error: No valid JSON array found in the Gemini response.")
            print(f"Raw response from Gemini: {result_text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        print(f"Response body: {response.text}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response from Gemini that caused the error: {result_text}")
        return None


def post_review_comments(comments):
    """Posts a list of comments to the GitHub pull request on the specific lines."""
    if not comments:
        print("No comments to post.")
        return

    # API URL for posting review comments on a PR
    comments_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls/{PR_NUMBER}/comments"

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    for comment in comments:
        payload = {
            'body': comment['comment'],
            'commit_id': COMMIT_ID,
            'path': comment['path'],
            'line': comment['line'],
        }

        try:
            response = requests.post(comments_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            print(f"Successfully posted comment to {comment['path']} at line {comment['line']}.")
        except requests.exceptions.RequestException as e:
            print(f"Error posting comment to {comment['path']} at line {comment['line']}: {e}")
            print(f"Response body: {response.text}")


# --- Main Execution ---

if __name__ == "__main__":
    print("Starting Gemini Line-by-Line Code Review...")
    pr_diff = get_pr_diff()

    if pr_diff:
        # Be mindful of token limits. For very large PRs, you might need to truncate the diff.
        if len(pr_diff) > 30000:
            print("PR diff is too large. Truncating.")
            pr_diff = pr_diff[:30000]

        review_comments = get_review_from_gemini(pr_diff)

        print(f"Full review received from Gemini (parsed):\n---\n{json.dumps(review_comments, indent=2)}\n---")

        if review_comments:
            post_review_comments(review_comments)
        else:
            print("No significant issues found by Gemini, or review was empty.")
    else:
        print("Could not retrieve PR diff. Exiting.")

    print("Review process finished.")