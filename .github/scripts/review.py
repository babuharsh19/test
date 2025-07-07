# .github/scripts/review.py

import os
import requests
import json
import subprocess
import re

# --- Constants and Configuration ---

# The model to use for the review. gemini-1.5-flash-latest provides the highest quality analysis.
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

# The maximum number of characters to send in the diff.
# The gemini-1.5-flash-latest model has a very large context window.
# 900k characters provide a large buffer.
MAX_DIFF_CHARS = 900_000

# --- Environment Variable Loading ---

# Securely load credentials and context from the GitHub Actions environment.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("PR_NUMBER")
COMMIT_ID = os.environ.get("COMMIT_ID")
BASE_BRANCH_NAME = os.environ.get('GITHUB_BASE_REF', 'main')

# Construct the Gemini API URL
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"


# --- Core Functions ---

def get_pr_diff():
    """
    Fetches the diff of the pull request using the 'git' command.
    This method is reliable in the GitHub Actions runner environment.

    Returns:
        str: The git diff as a string, or None if an error occurs.
    """
    print(f"Fetching diff between '{BASE_BRANCH_NAME}' and commit '{COMMIT_ID[:7]}'.")
    try:
        # Ensure the base branch is fetched to be available for diffing.
        subprocess.run(['git', 'fetch', 'origin', BASE_BRANCH_NAME], check=True, capture_output=True, text=True)

        # Get the diff. The '...' syntax compares the tip of the current branch with the merge base of the target branch.
        diff_command = ['git', 'diff', f'origin/{BASE_BRANCH_NAME}...{COMMIT_ID}']
        result = subprocess.run(diff_command, capture_output=True, text=True, check=True)

        print("Successfully fetched PR diff.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        # Log detailed errors if the git command fails.
        print(f"Error getting git diff: {e}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        return None


def get_review_from_gemini(diff: str):
    """
    Sends the code diff to the Gemini API for review and parses the response.

    Args:
        diff (str): The code changes in diff format.

    Returns:
        list: A list of comment objects, or None if an error occurs.
    """
    if not diff:
        print("No diff content to review.")
        return None

    # This comprehensive prompt is engineered to guide the AI to act as an expert reviewer
    # and provide its feedback in a structured JSON format.
    prompt = f"""
    You are an expert Staff Software Engineer and a meticulous code reviewer, fluent in Python, JavaScript, HTML, and CSS. Your task is to review a pull request based on the provided git diff.

    Please analyze the diff with the following priorities, providing detailed, constructive, and actionable feedback.

    **1. Critical Security Analysis:**
    - **Hardcoded Secrets:** Identify any hardcoded API keys, passwords, or other credentials. This is a CRITICAL issue.
    - **Injection Vulnerabilities:** Look for potential SQL injection, Cross-Site Scripting (XSS), or command injection flaws.
    - **Insecure Practices:** Check for use of weak cryptographic algorithms, disabled security features (e.g., CSRF protection), or insecure handling of file uploads.

    **2. Logic, Correctness, and Edge Cases:**
    - **Bugs and Flaws:** Identify potential bugs, logic errors, off-by-one errors, and race conditions.
    - **Edge Cases:** Consider how the code handles unexpected or invalid inputs, empty lists, null values, etc.
    - **Error Handling:** Is error handling robust? Does it catch specific exceptions? Does it leak sensitive information in error messages?

    **3. Performance and Efficiency:**
    - **Algorithmic Complexity:** Are there inefficient loops (O(n^2)) that could be optimized?
    - **Resource Management:** Look for potential memory leaks, unclosed file handles, or inefficient database queries (e.g., N+1 queries).
    - **Redundancy:** Identify redundant computations, API calls, or checks inside loops.

    **4. Architecture and Design:**
    - **Design Principles:** Does the code adhere to SOLID, DRY (Don't Repeat Yourself), and KISS (Keep It Simple, Stupid) principles?
    - **Code Smells:** Identify issues like tight coupling, low cohesion, "god objects," or very long methods.
    - **Scalability:** Are there architectural choices that might hinder future scalability?

    **5. Maintainability and Readability:**
    - **Clarity:** Is the code clear, concise, and easy to understand?
    - **Naming:** Are variables, functions, and classes named descriptively?
    - **Comments:** Are there comments for complex or non-obvious logic? Are the existing comments accurate?
    
    **6. Approach and correctness:**
    - **Approach:** Is the approach taken for code is best approach or any alternative approach would have been better
    - **Performance:** Is the code optimized for performance?
    - **Syntax:** Is the correct syntax used in the code?
    - **Need:** Is the code change unnecessary and not needed or redundant and duplicate?
    - **Principles:** Is the variable naming, comments and docstrings etc. are correct?

    **Output Format Instructions:**
    - Provide your feedback as a clean JSON array of objects.
    - Each object must represent a single, specific comment and have the following structure:
      `{{
          "path": "<The full path to the file>",
          "line": <The line number in the new file where the issue is located>,
          "comment": "<Your detailed and actionable review comment. Suggest the correct code or approach.>"
      }}`
    - The 'line' number **must** be a line that was added or modified in the diff.
    - If there are absolutely no issues to report, return an empty JSON array: `[]`.
    - Do not include any text, pleasantries, or markdown formatting outside of the JSON array itself.

    Here is the diff to review:
    ```diff
    {diff}
    ```
    """

    # Prepare the payload for the Gemini API.
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # Add generation config to ensure JSON output
        "generationConfig": {
            "responseMimeType": "application/json",
        }
    }
    headers = {'Content-Type': 'application/json'}
    raw_response_text = ""

    try:
        print("Sending request to Gemini API...")
        response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        raw_response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        print("Successfully received response from Gemini API.")

        # The response should be a clean JSON string because of responseMimeType.
        return json.loads(raw_response_text)

    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        if e.response:
            print(f"Response body: {e.response.text}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini response structure: {e}")
        print(f"Raw response received: {raw_response_text}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Gemini response: {e}")
        print(f"Raw response received that caused the error: {raw_response_text}")
        return None


def post_review_comments(comments: list):
    """
    Posts a list of review comments to the GitHub pull request.

    Args:
        comments (list): A list of comment objects from the Gemini review.
    """
    if not comments:
        print("No comments to post.")
        return

    print(f"Posting {len(comments)} comments to PR #{PR_NUMBER}...")

    # API endpoint for creating review comments on a pull request.
    comments_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls/{PR_NUMBER}/comments"

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    for comment in comments:
        # Validate that the comment object has the required keys.
        if not all(k in comment for k in ["path", "line", "comment"]):
            print(f"Skipping malformed comment object: {comment}")
            continue

        payload = {
            'body': comment['comment'],
            'commit_id': COMMIT_ID,
            'path': comment['path'],
            'line': comment['line'],
        }

        try:
            response = requests.post(comments_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            print(f"Successfully posted comment to '{comment['path']}' at line {comment['line']}.")
        except requests.exceptions.RequestException as e:
            print(f"Error posting comment to '{comment['path']}' at line {comment['line']}: {e}")
            print(f"Response body: {e.response.text}")


# --- Main Execution Block ---

if __name__ == "__main__":
    print("--- Starting Gemini Code Review ---")

    # Validate that all necessary environment variables are set.
    if not all([GEMINI_API_KEY, GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER, COMMIT_ID]):
        print("Error: Missing one or more required environment variables. Exiting.")
        exit(1)

    pr_diff = get_pr_diff()

    if pr_diff:
        # Truncate the diff if it exceeds the maximum character limit.
        if len(pr_diff) > MAX_DIFF_CHARS:
            print(f"Warning: PR diff is very large ({len(pr_diff)} chars). Truncating to {MAX_DIFF_CHARS} chars.")
            pr_diff = pr_diff[:MAX_DIFF_CHARS]

        review_comments = get_review_from_gemini(pr_diff)

        # Log the parsed review for debugging purposes.
        print(f"Gemini review (parsed):\n---\n{json.dumps(review_comments, indent=2)}\n---")

        if review_comments:
            post_review_comments(review_comments)
        else:
            print("No actionable issues found by Gemini, or the review was empty.")
    else:
        print("Could not retrieve PR diff. Exiting.")

    print("--- Review Process Finished ---")
