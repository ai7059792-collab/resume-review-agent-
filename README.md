# AI Resume Review Agent

A beginner-friendly Streamlit application that reviews a candidate's resume
against a target job description.

## Stack

- Python 3.11
- Streamlit
- CrewAI
- Groq
- OpenAI GPT-OSS 120B: `openai/gpt-oss-120b`
- pypdf for PDF text extraction

Groq currently lists `openai/gpt-oss-120b` as a production model with a
131,072-token context window. Groq also lists Llama 3.3 70B as deprecated,
with GPT-OSS 120B as a recommended replacement.

## Files

```text
resume-review-agent/
├── app.py
├── workflow_prompts.py
├── requirements.txt
└── README.md
```

## 1. Get a Groq API key

Create a Groq API key from the Groq console.

Do not paste the key into `app.py` and do not commit it to GitHub.

## 2. Streamlit Cloud secrets

In Streamlit Cloud:

1. Open your deployed app.
2. Open **Settings / Secrets**.
3. Add:

```toml
GROQ_API_KEY = "your_groq_api_key_here"
```

Save the secret and restart/redeploy the app.

## 3. GitHub

Create a repository and upload:

- `app.py`
- `workflow_prompts.py`
- `requirements.txt`
- `README.md`

## 4. Deploy

On Streamlit Community Cloud:

1. Create a new app.
2. Select your GitHub repository.
3. Select `app.py` as the main file.
4. Deploy.
5. Add `GROQ_API_KEY` in Secrets.
6. Reboot the app.

## 5. Run locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install:

```bash
pip install -r requirements.txt
```

Set the API key.

PowerShell:

```powershell
$env:GROQ_API_KEY="your_key_here"
```

Run:

```bash
streamlit run app.py
```

## How the application works

```text
Resume PDF
    ↓
PDF text extraction
    ↓
Input validation
    ↓
Single CrewAI Resume Reviewer Agent
    ↓
Groq: openai/gpt-oss-120b
    ↓
Structured Markdown review
    ↓
Downloadable report
```

The application also has a small direct-Groq fallback for transient
CrewAI/LiteLLM provider errors.

## Important implementation note

The application intentionally uses the normal CrewAI `Agent` + `Task` +
`Crew` path rather than CrewAI Flow. This keeps the project simple and avoids
adding unsupported provider-specific request fields such as
`cache_breakpoint` to Groq requests.

## Troubleshooting

### "GROQ_API_KEY is not configured"

Add the key to Streamlit Secrets exactly as:

```toml
GROQ_API_KEY = "your_key_here"
```

### PDF extraction returns no text

The resume may be an image-only scanned PDF. Use a text-based PDF or add an
OCR step.

### Rate limit / 429

Groq enforces request and token limits. Wait briefly and try again, or reduce
the amount of text submitted.

### Model error

Confirm that the model name is exactly:

```text
openai/gpt-oss-120b
```

Do not use the old Llama model name.

### CrewAI/LiteLLM provider error

The app automatically attempts a direct Groq-compatible API call once after
the CrewAI path fails. If both fail, check the full error shown by Streamlit
and verify the API key and package versions.

## Security

Never commit:

- API keys
- `.streamlit/secrets.toml`
- `.env`

Add this to `.gitignore`:

```text
.streamlit/secrets.toml
.env
__pycache__/
.venv/
```
