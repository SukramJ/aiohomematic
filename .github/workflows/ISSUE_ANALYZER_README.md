# Issue Analyzer Workflow

This GitHub Actions workflow automatically **triages** newly created issues. It deliberately
does **not** diagnose root causes: an audit of 181 bot-commented issues (2026-07) showed that
LLM root-cause analyses were fully correct in only 18% of cases and outright wrong in 24%,
while the data-collection parts (missing diagnostics/log requests) were the reliably useful
ones. The bot therefore focuses on deterministic checks; do not re-add diagnosis sections.

## What the bot does

1. **Checks required raw data (deterministic)**
   - Detects attached integration diagnostics (.json) and log files (including inline log
     excerpts in fenced code blocks)
   - Requests missing data and maintains the `needs-raw-data` triage label

2. **Validates the reported version (deterministic)**
   - Parses the version from the issue-form field (not from free text)
   - Compares it against the actually published releases of
     [homematicip_local](https://github.com/sukramj/homematicip_local/releases)
   - Posts a *neutral* notice when the version is outdated or matches no published release —
     never a "critical" banner

3. **Detects pasted AI analyses (deterministic)**
   - Flags reports that contain an AI-generated interpretation instead of raw data and
     redirects the reporter to attach the underlying files

4. **Searches for similar issues (GitHub search API)**
   - Uses the device model (extracted deterministically) plus LLM-suggested search terms
   - Queries the real GitHub search API (the previous implementation listed the most
     recently updated issues regardless of relevance)

5. **Uses Claude only for triage, not diagnosis**
   - A short summary (max. 2 sentences), 0-2 documentation links, search terms, and
     routing flags (device-related, feature request)
   - The prompt contains the current date and forbids root-cause claims
   - If the Claude call fails, the deterministic triage comment is still posted

6. **Multilingual support**
   - Detects the template language (German/English) and responds in it

## Companion workflow: Close Issue - Insufficient Information

`close-insufficient-info.yml` closes an issue that lacks the required data. It is triggered
manually (`workflow_dispatch`) and protects against premature closes with guardrails:

- refuses to close when the issue contains attachments, screenshots, or inline log excerpts
- refuses to close issues labeled as feature requests (`enhancement`/`feature`)
- enforces a minimum waiting period of **72 hours** after the `needs-raw-data` label was
  applied (or after issue creation), giving reporters time to supply the data
- `force: true` input overrides all guardrails

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

2. **Optional: pin the Claude model**
   - Repository variable `ANALYZER_MODEL` overrides the default model used for the
     triage summary (no code change needed when a model is renamed)

3. **Activate workflow**
   - The workflow is automatically active after adding the secret
   - It runs on every newly created or edited issue (a comment is only posted once)

### Permissions

The workflow requires the following permissions (already configured):

- `issues: write` - To post comments and maintain labels
- `contents: read` - To read the repository

## Comment structure

A posted comment can contain (only sections with content are rendered):

- Summary (LLM, descriptive only)
- Version notice (deterministic: outdated / unknown version)
- Missing required information (diagnostics / log / version field)
- Raw-data redirect when a pasted AI analysis was detected
- Feature-request routing hint (pointing to the discussions)
- Screenshot hint for device-related issues
- Helpful documentation (max. 2 links)
- Similar issues (search-API results)

If none of the sections has content, no comment is posted.

## Customization

- **Documentation links**: `DOCS_LINKS` in `.github/scripts/analyze_issue.py`
- **Triage prompt**: `CLAUDE_TRIAGE_PROMPT` in `analyze_issue.py` (keep the no-diagnosis rules!)
- **Version-field markers**: `VERSION_FIELD_MARKERS` (update when the issue-template labels change)

## Costs

- One Claude call per issue with a small output budget (max. 600 tokens)
- Estimated costs: well below $0.01-0.03 per issue

## Troubleshooting

### Workflow is not running

- Check if the `ANTHROPIC_API_KEY` secret is set
- Review the workflow logs under Actions → Issue Analyzer

### Comment is not posted

- The workflow only posts when at least one section has content
- Check the logs for error messages

### API errors

- Make sure the API key is valid
- Check your Anthropic account for sufficient credits
- The deterministic checks still run and post when the Claude call fails

## Deactivation

To deactivate the workflow:

1. Delete or rename the file `.github/workflows/issue-analyzer.yml`
2. Or add at the beginning:
   ```yaml
   on:
     workflow_dispatch: # Only manually executable
   ```
