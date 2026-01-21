"""Claude Code CLI Integration for Email Classification"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from logger import setup_logger

logger = setup_logger('claude_code')

PROCESSING_DIR = Path(__file__).parent / ".claude-processing"


def check_claude_code_installed() -> bool:
    """Check if Claude Code CLI is installed"""
    try:
        result = subprocess.run(
            ['which', 'claude'],
            capture_output=True,
            text=True,
            timeout=5
        )
        installed = result.returncode == 0 and result.stdout.strip()
        logger.info(f"Claude Code installed: {installed}")
        return installed
    except Exception as e:
        logger.error(f"Error checking for Claude Code: {e}")
        return False


def export_emails_for_claude(emails: List[Dict], output_file: str = "emails.json") -> str:
    """
    Export emails to JSON file for Claude Code processing

    Args:
        emails: List of email dictionaries
        output_file: Filename for output (in .claude-processing/)

    Returns:
        Path to exported file
    """
    PROCESSING_DIR.mkdir(exist_ok=True)

    # Simplify emails to only what's needed
    simplified_emails = []
    for email in emails:
        simplified_emails.append({
            'id': email.get('email_id', ''),
            'from': email.get('sender', ''),
            'subject': email.get('subject', ''),
            'date': email.get('date', '')
        })

    output_path = PROCESSING_DIR / output_file

    with open(output_path, 'w') as f:
        json.dump(simplified_emails, f, indent=2)

    logger.info(f"Exported {len(simplified_emails)} emails to {output_path}")
    return str(output_path)


def create_classification_prompt(categories: Dict, job_search_focused: bool = True) -> str:
    """
    Create the prompt for Claude Code to classify emails

    Args:
        categories: Category definitions from config
        job_search_focused: Whether to prioritize job search categories

    Returns:
        Path to prompt file
    """
    PROCESSING_DIR.mkdir(exist_ok=True)

    prompt_path = PROCESSING_DIR / "prompt.md"

    # Build category list
    category_list = []
    for group_name, group_categories in categories.items():
        for key, info in group_categories.items():
            category_list.append(f"- **{key}**: {info['name']} - {info['description']}")

    prompt = f"""# Email Classification Task

You are analyzing emails to categorize them for better organization.

## Available Categories:
{chr(10).join(category_list)}

## Input Data:
The emails are in `.claude-processing/emails.json`

## Your Task:
1. Read all emails from `emails.json`
2. Classify each email into one of the categories above
3. Output results to `.claude-processing/results.json`

## Output Format:
```json
[
  {{
    "id": "email_id_here",
    "category": "category_key",
    "confidence": 0.95
  }}
]
```

## Important:
- Use only the "from" and "subject" fields to classify (no body needed)
- Be accurate - these will create Gmail labels
- {"Focus on job search categories" if job_search_focused else "Treat all categories equally"}
- Output MUST be valid JSON array

Please process all emails and save the results.
"""

    with open(prompt_path, 'w') as f:
        f.write(prompt)

    logger.info(f"Created classification prompt at {prompt_path}")
    return str(prompt_path)


def launch_claude_code_terminal(prompt_file: str) -> None:
    """
    Opens Terminal and runs Claude Code with the prompt

    Args:
        prompt_file: Path to the prompt file
    """
    project_dir = Path(__file__).parent

    # Create AppleScript to open Terminal and run Claude Code
    applescript = f'''
tell application "Terminal"
    activate
    do script "cd {project_dir} && echo '🤖 Starting Claude Code classification...' && claude --dangerously-skip-permissions < {prompt_file} && echo '' && echo '✓ Classification complete! Check .claude-processing/results.json' && echo '' && echo 'Press Enter to return to the app...' && read"
end tell
'''

    try:
        subprocess.run(
            ['osascript', '-e', applescript],
            check=True
        )
        logger.info("Launched Claude Code in Terminal")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Terminal: {e}")
        raise


def read_classification_results() -> Optional[List[Dict]]:
    """
    Read classification results from Claude Code output

    Returns:
        List of classification results or None if not ready
    """
    results_path = PROCESSING_DIR / "results.json"

    if not results_path.exists():
        logger.warning(f"Results file not found: {results_path}")
        return None

    try:
        with open(results_path, 'r') as f:
            results = json.load(f)

        logger.info(f"Read {len(results)} classification results")
        return results

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in results file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading results: {e}")
        return None


def cleanup_processing_files():
    """Remove all files from .claude-processing/"""
    try:
        for file in PROCESSING_DIR.glob("*"):
            file.unlink()
        logger.info("Cleaned up processing files")
    except Exception as e:
        logger.error(f"Error cleaning up: {e}")


if __name__ == "__main__":
    # Test Claude Code detection
    if check_claude_code_installed():
        print("✓ Claude Code is installed")
    else:
        print("✗ Claude Code not found")
