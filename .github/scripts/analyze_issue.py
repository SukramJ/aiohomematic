#!/usr/bin/env python3
"""
Issue analyzer script for AioHomematic and Homematic(IP) Local.

This script uses Claude AI to analyze newly created issues and provide helpful feedback.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, cast

from anthropic import Anthropic
from github import Auth, Github, GithubException, Repository

# Documentation links
DOCS_LINKS = {
    "main_readme": "https://github.com/SukramJ/aiohomematic/blob/devel/README.md",
    "homematicip_local_readme": "https://github.com/sukramj/homematicip_local#homematicip_local",
    "troubleshooting": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/homeassistant_troubleshooting.md",
    "faqs": "https://github.com/sukramj/homematicip_local#frequently-asked-questions",
    "installation": "https://github.com/sukramj/homematicip_local/wiki/Installation",
    "releases": "https://github.com/sukramj/homematicip_local/releases",
    "architecture": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/architecture.md",
    "naming": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/naming.md",
    "unignore": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/unignore.md",
    "input_select_helper": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/input_select_helper.md",
    "lifecycle": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/homeassistant_lifecycle.md",
    "discussions": "https://github.com/sukramj/aiohomematic/discussions",
}

# Required information fields from issue template
REQUIRED_FIELDS = [
    "version",
    "installation_type",
    "backend_type",
    "problem_description",
]

CLAUDE_ANALYSIS_PROMPT = """You are an AI assistant helping to analyze GitHub issues for the AioHomematic and Homematic(IP) Local projects.

Context:
- This repository (aiohomematic) is a Python library for controlling Homematic and HomematicIP devices
- Issues may relate to either the library itself or the Home Assistant integration "Homematic(IP) Local"
- Issues should follow a specific template with required information

Your task:
1. Analyze the issue content and determine if it's complete and well-formed
2. Identify any missing required information:
   - Version of Homematic(IP) Local integration
   - Type of Home Assistant installation
   - Type of Homematic backend (CCU3, RaspberryMatic, etc.)
   - Clear problem description
   - Diagnostics data (if applicable)
   - Protocol/log file (if applicable)
3. Suggest relevant documentation links from the available docs
4. Identify key terms for searching similar issues

Issue Title: {title}

Issue Body:
{body}

Available documentation:
{docs}

Please respond in JSON format with the following structure:
{{
  "is_complete": boolean,
  "missing_information": [
    {{
      "field": "field name",
      "description": "what information is missing",
      "language": "de" or "en" (detected from issue)
    }}
  ],
  "suggested_docs": [
    {{
      "doc_key": "key from available docs",
      "reason": "why this doc is relevant"
    }}
  ],
  "search_terms": ["term1", "term2", ...],
  "language": "de" or "en",
  "is_bug_report": boolean,
  "summary": "brief summary of the issue in the detected language"
}}

Be helpful and constructive. Only flag missing information if it's genuinely required to help solve the issue."""


def get_claude_analysis(title: str, body: str, api_key: str) -> dict[str, Any]:
    """Use Claude to analyze the issue."""
    client = Anthropic(api_key=api_key)

    docs_str = "\n".join([f"- {key}: {url}" for key, url in DOCS_LINKS.items()])

    prompt = CLAUDE_ANALYSIS_PROMPT.format(title=title, body=body or "(empty)", docs=docs_str)

    message = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=2000, messages=[{"role": "user", "content": prompt}]
    )

    # Parse the JSON response
    response_text = message.content[0].text
    # Extract JSON from potential markdown code blocks
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    return cast(dict[str, Any], json.loads(response_text))


def search_similar_issues(
    repo: Repository.Repository, search_terms: list[str], current_issue_number: int
) -> list[dict[str, Any]]:
    """Search for similar issues and discussions."""
    similar_items: list[dict[str, Any]] = []

    # Limit search terms to top 3 most relevant
    search_terms = search_terms[:3]

    for term in search_terms:
        if not term or len(term) < 3:
            continue

        # Search in issues
        try:
            issues = repo.get_issues(state="all", sort="updated", direction="desc")
            similar_items.extend(
                {
                    "type": "issue",
                    "number": issue.number,
                    "title": issue.title,
                    "url": issue.html_url,
                    "state": issue.state,
                    "search_term": term,
                }
                for issue in issues[:5]  # Limit to 5 results per term
                if issue.number != current_issue_number
            )
        except GithubException:
            pass

    # Remove duplicates
    seen = set()
    unique_items = []
    for item in similar_items:
        key = (item["type"], item["number"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items[:5]  # Return top 5 overall


def has_bot_comment(issue: Any) -> bool:
    """Check if the bot has already commented on this issue."""
    for comment in issue.get_comments():
        if comment.user.type == "Bot" and "Automatische Issue-Analyse" in comment.body:
            return True
        if comment.user.type == "Bot" and "Automatic Issue Analysis" in comment.body:
            return True
    return False


def format_comment(analysis: dict[str, Any], similar_items: list[dict[str, Any]]) -> str:
    """Format the comment to post on the issue."""
    lang = analysis.get("language", "en")
    is_german = lang == "de"

    # Header
    if is_german:
        comment = "## Automatische Issue-Analyse\n\n"
        comment += f"**Zusammenfassung:** {analysis.get('summary', 'Issue wurde erkannt')}\n\n"
    else:
        comment = "## Automatic Issue Analysis\n\n"
        comment += f"**Summary:** {analysis.get('summary', 'Issue detected')}\n\n"

    # Missing information
    missing = analysis.get("missing_information", [])
    if missing:
        if is_german:
            comment += "### Fehlende Informationen\n\n"
            comment += "Um dir besser helfen zu können, fehlen noch folgende Informationen:\n\n"
        else:
            comment += "### Missing Information\n\n"
            comment += "To help you better, the following information is missing:\n\n"

        for item in missing:
            comment += f"- **{item['field']}**: {item['description']}\n"
        comment += "\n"

    # Suggested documentation
    suggested_docs = analysis.get("suggested_docs", [])
    if suggested_docs:
        if is_german:
            comment += "### Hilfreiche Dokumentation\n\n"
            comment += "Die folgenden Dokumentationsseiten könnten hilfreich sein:\n\n"
        else:
            comment += "### Helpful Documentation\n\n"
            comment += "The following documentation pages might be helpful:\n\n"

        for doc in suggested_docs:
            doc_key = doc["doc_key"]
            if doc_key in DOCS_LINKS:
                url = DOCS_LINKS[doc_key]
                reason = doc["reason"]
                comment += f"- [{doc_key}]({url})\n  _{reason}_\n"
        comment += "\n"

    # Similar issues
    if similar_items:
        if is_german:
            comment += "### Ähnliche Issues und Diskussionen\n\n"
            comment += "Die folgenden Issues oder Diskussionen könnten relevant sein:\n\n"
        else:
            comment += "### Similar Issues and Discussions\n\n"
            comment += "The following issues or discussions might be relevant:\n\n"

        for item in similar_items:
            state_emoji = "✅" if item["state"] == "closed" else "🔄"
            comment += f"- {state_emoji} #{item['number']}: [{item['title']}]({item['url']})\n"
        comment += "\n"

    # Footer
    if is_german:
        comment += "---\n"
        comment += "_Diese Analyse wurde automatisch erstellt. "
        comment += "Bei Fragen oder Problemen, bitte die [Diskussionen]({}) nutzen._\n".format(
            DOCS_LINKS["discussions"]
        )
    else:
        comment += "---\n"
        comment += "_This analysis was generated automatically. "
        comment += "For questions or support, please use the [discussions]({})._\n".format(DOCS_LINKS["discussions"])

    return comment


def main() -> None:
    """Analyze issue and post comment."""
    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN") or ""
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
    issue_number = int(os.getenv("ISSUE_NUMBER", "0"))
    repo_name = os.getenv("REPO_NAME", "")

    if not all([github_token, anthropic_api_key, issue_number, repo_name]):
        print("Error: Missing required environment variables")  # noqa: T201
        sys.exit(1)

    # Initialize GitHub client
    gh = Github(auth=Auth.Token(github_token))
    repo = gh.get_repo(repo_name)
    issue = repo.get_issue(issue_number)

    # Get issue details (either from env or from GitHub API)
    issue_title = os.getenv("ISSUE_TITLE") or issue.title
    issue_body = os.getenv("ISSUE_BODY") or issue.body or ""

    print(f"Analyzing issue #{issue_number}: {issue_title}")  # noqa: T201

    # Get Claude's analysis
    try:
        analysis = get_claude_analysis(issue_title, issue_body, anthropic_api_key)
        print(f"Analysis complete: {json.dumps(analysis, indent=2)}")  # noqa: T201
    except Exception as e:
        print(f"Error getting Claude analysis: {e}")  # noqa: T201
        sys.exit(1)

    # Search for similar issues
    search_terms = analysis.get("search_terms", [])
    similar_items = []
    if search_terms:
        try:
            similar_items = search_similar_issues(repo, search_terms, issue_number)
            print(f"Found {len(similar_items)} similar items")  # noqa: T201
        except Exception as e:
            print(f"Error searching for similar issues: {e}")  # noqa: T201

    # Check if bot has already commented (to avoid duplicates on edit)
    is_manual_trigger = not os.getenv("ISSUE_TITLE")  # Manual trigger doesn't have ISSUE_TITLE in env
    already_commented = has_bot_comment(issue)

    if already_commented and not is_manual_trigger:
        print("Bot has already commented on this issue, skipping to avoid duplicates")  # noqa: T201
        return

    # Format and post comment
    comment_body = format_comment(analysis, similar_items)

    # Only post if there's something useful to say
    if analysis.get("missing_information") or analysis.get("suggested_docs") or similar_items:
        try:
            issue.create_comment(comment_body)
            print("Comment posted successfully")  # noqa: T201
        except Exception as e:
            print(f"Error posting comment: {e}")  # noqa: T201
            sys.exit(1)
    else:
        print("No actionable feedback to provide, skipping comment")  # noqa: T201


if __name__ == "__main__":
    main()
