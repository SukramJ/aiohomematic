# Issue Analyzer Workflow

This GitHub Actions workflow automatically analyzes newly created issues and provides helpful feedback.

## Features

The workflow uses Claude AI to:

1. **Identify missing information**
   - Checks if all required fields from the issue template have been filled out
   - Requests missing information (version, installation type, backend type, etc.)

2. **Suggest relevant documentation**
   - References appropriate documentation pages in both repositories:
     - AioHomematic README and Docs
     - Homematic(IP) Local README and Wiki
   - Considers troubleshooting guides and FAQs

3. **Find similar issues and discussions**
   - Searches for similar issues (both open and closed)
   - Helps avoid duplicates and find existing solutions

4. **Multilingual support**
   - Automatically detects the language (German/English)
   - Responds in the detected language

## Setup

### Prerequisites

To activate the workflow, you need an Anthropic API key:

1. Create an account at [Anthropic](https://console.anthropic.com/)
2. Generate an API key

### Configuration

1. **Add GitHub Secret**
   - Go to: Repository Settings → Secrets and variables → Actions
   - Click on "New repository secret"
   - Name: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key

2. **Activate workflow**
   - The workflow is automatically active after adding the secret
   - It will run on every newly created issue

### Permissions

The workflow requires the following permissions (already configured):
- `issues: write` - To post comments
- `contents: read` - To read the repository

## How it works

1. **Trigger**: When a new issue is created
2. **Analysis**: Claude AI analyzes:
   - Title and content of the issue
   - Compliance with template requirements
   - Relevant topics and keywords
3. **Search**: Searches for similar issues in the repository
4. **Comment**: Posts a helpful comment with:
   - Summary
   - List of missing information (if any)
   - Relevant documentation links
   - Similar issues/discussions

## Example Comment

```markdown
## Automatic Issue Analysis

**Summary:** Connection problem with CCU3 via HTTPS

### Missing Information

To help you better, the following information is missing:

- **Diagnostics data**: Please upload the diagnostics data for the affected device
- **Protocol file**: The complete log helps with troubleshooting

### Helpful Documentation

The following documentation pages might be helpful:

- [troubleshooting](https://github.com/SukramJ/aiohomematic/blob/devel/docs/homeassistant_troubleshooting.md)
  _Contains solutions for common connection problems_
- [installation](https://github.com/sukramj/homematicip_local/wiki/Installation)
  _Guide for correct TLS configuration_

### Similar Issues and Discussions

The following issues or discussions might be relevant:

- ✅ #1234: [HTTPS connection fails with self-signed certificate](https://github.com/...)
- 🔄 #1456: [CCU3 connection timeout](https://github.com/...)

---
_This analysis was generated automatically. For questions or problems, please use the discussions._
```

## Customization

### Customize documentation links

The available documentation links are defined in `.github/scripts/analyze_issue.py`:

```python
DOCS_LINKS = {
    "main_readme": "https://github.com/SukramJ/aiohomematic/blob/devel/README.md",
    "homematicip_local_readme": "https://github.com/sukramj/homematicip_local#homematicip_local",
    "troubleshooting": "https://github.com/SukramJ/aiohomematic/blob/devel/docs/homeassistant_troubleshooting.md",
    # ... more links
}
```

### Customize analysis prompt

The analysis prompt can be customized in the variable `CLAUDE_ANALYSIS_PROMPT` in `analyze_issue.py`.

## Costs

- The workflow uses Claude 3.5 Sonnet
- Estimated costs: ~$0.01-0.03 per issue analysis
- Depends on issue length and complexity

## Troubleshooting

### Workflow is not running

- Check if the `ANTHROPIC_API_KEY` secret is set
- Review the workflow logs under Actions → Issue Analyzer

### Comment is not posted

- Workflow only posts if there is helpful information to provide
- Check the logs for error messages

### API errors

- Make sure the API key is valid
- Check your Anthropic account for sufficient credits

## Deactivation

To deactivate the workflow:
1. Delete or rename the file `.github/workflows/issue-analyzer.yml`
2. Or add at the beginning:
   ```yaml
   on:
     workflow_dispatch:  # Only manually executable
   ```
