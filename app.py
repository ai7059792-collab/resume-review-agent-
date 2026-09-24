import os
import sys
import time
from io import BytesIO

import streamlit as st
from pypdf import PdfReader

from workflow_prompts import SYSTEM_PROMPT, TASK_PROMPT


# ---------------------------------------------------------
# App configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Resume Review Agent",
    page_icon="📄",
    layout="wide",
)


MODEL_NAME = "openai/gpt-oss-120b"
SUPPORTED_PYTHON = (3, 11)


# CrewAI currently requires Python >=3.10 and <3.14. Streamlit Cloud can
# run Python 3.14, but this application intentionally uses Python 3.11 for
# CrewAI/ChromaDB/Pydantic compatibility.
if sys.version_info[:2] != SUPPORTED_PYTHON:
    st.error(
        "This application must run on Python 3.11. "
        f"Current Python version: {sys.version.split()[0]}"
    )
    st.info(
        "In Streamlit Community Cloud, redeploy the app and select "
        "Python 3.11 under Advanced settings."
    )
    st.stop()


# Import CrewAI only after the Python-version check. This prevents a long,
# confusing Pydantic/ChromaDB traceback when the wrong Python runtime is used.
try:
    from crewai import Agent, Crew, LLM, Process, Task
except Exception as exc:
    st.error("CrewAI could not be imported in this environment.")
    st.code(str(exc))
    st.info(
        "Use Python 3.11 and the pinned dependencies in requirements.txt, "
        "then redeploy the Streamlit app."
    )
    st.stop()


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------
def get_groq_api_key():
    """Read the Groq API key from Streamlit secrets or environment variables."""
    key = None

    # Streamlit Cloud / local .streamlit/secrets.toml
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None

    # Local environment variable fallback
    if not key:
        key = os.getenv("GROQ_API_KEY")

    if key:
        return str(key).strip()

    return None


def extract_pdf_text(uploaded_file):
    """Extract text from a PDF uploaded to Streamlit."""
    try:
        pdf_bytes = uploaded_file.getvalue()

        if not pdf_bytes:
            raise ValueError("The uploaded PDF is empty.")

        reader = PdfReader(BytesIO(pdf_bytes))

        if not reader.pages:
            raise ValueError("The PDF contains no readable pages.")

        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {page_number}]\n{text.strip()}")
            except Exception:
                # Continue extracting other pages if one page has a problem.
                continue

        full_text = "\n\n".join(pages).strip()

        if not full_text:
            raise ValueError(
                "No selectable text could be extracted from this PDF. "
                "If the resume is a scanned image, OCR is required."
            )

        return full_text

    except Exception as exc:
        raise RuntimeError(f"PDF extraction failed: {exc}") from exc


def clean_text(text, max_chars):
    """Keep prompts within a practical size for hosted API limits."""
    text = (text or "").strip()

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n\n[Content truncated by the application to keep the request compact.]"
    )


def create_resume_agent(api_key):
    """
    Create one CrewAI agent using Groq's OpenAI GPT-OSS 120B model.

    Important:
    We use the normal CrewAI Agent/Crew path rather than CrewAI Flow.
    This keeps the project simple and avoids adding unsupported request fields
    such as cache_breakpoint to Groq requests.
    """
    # CrewAI/LiteLLM can read the provider key from this environment variable.
    os.environ["GROQ_API_KEY"] = api_key

    llm = LLM(
        model=f"groq/{MODEL_NAME}",
        api_key=api_key,
        temperature=0.2,
        max_tokens=5000,
    )

    return Agent(
        role="Expert Resume Reviewer",
        goal=(
            "Accurately compare a candidate resume with a target job "
            "description and produce a structured, actionable review."
        ),
        backstory=(
            "You are an experienced technical recruiter and resume coach. "
            "You are careful with evidence and never invent candidate facts."
        ),
        system_template=SYSTEM_PROMPT,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def review_with_crewai(api_key, resume_text, job_description):
    """Run the single CrewAI agent."""
    agent = create_resume_agent(api_key)

    task = Task(
        description=TASK_PROMPT.format(
            resume_text=resume_text,
            job_description=job_description,
        ),
        expected_output=(
            "A clean Markdown resume review containing all seven requested "
            "sections, with evidence-based matches and actionable improvements."
        ),
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()

    # CrewAI result objects normally stringify cleanly.
    output = str(result).strip()

    if not output:
        raise RuntimeError("The AI returned an empty review.")

    return output


def direct_groq_fallback(api_key, resume_text, job_description):
    """
    Minimal fallback for transient CrewAI/LiteLLM compatibility issues.

    The normal path is CrewAI. This fallback uses Groq's OpenAI-compatible API
    directly so a temporary agent-framework integration error does not make
    the Streamlit app unusable.
    """
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TASK_PROMPT.format(
                        resume_text=resume_text,
                        job_description=job_description,
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=5000,
        )

        output = response.choices[0].message.content

        if not output:
            raise RuntimeError("Groq returned an empty response.")

        return output.strip()

    except Exception as exc:
        raise RuntimeError(
            "Direct Groq fallback also failed. "
            f"Original error: {exc}"
        ) from exc


# ---------------------------------------------------------
# User interface
# ---------------------------------------------------------
st.title("📄 AI Resume Review Agent")
st.caption(
    "Beginner-friendly single-agent resume analysis using CrewAI + "
    "Groq + OpenAI GPT-OSS 120B."
)

with st.sidebar:
    st.header("⚙️ Configuration")
    st.write(f"**Model:** `{MODEL_NAME}`")
    st.write("**Provider:** Groq")
    st.write("**Agent framework:** CrewAI")
    st.divider()
    st.info(
        "Add your Groq key as `GROQ_API_KEY` in Streamlit Secrets. "
        "Never put the key directly inside app.py."
    )

api_key = get_groq_api_key()

if not api_key:
    st.warning(
        "GROQ_API_KEY is not configured yet. Add it in Streamlit Cloud "
        "Secrets or as a local environment variable."
    )

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Candidate Resume")
    uploaded_pdf = st.file_uploader(
        "Upload resume PDF",
        type=["pdf"],
        help="Upload a text-based PDF resume. Scanned image-only PDFs need OCR.",
    )

with col2:
    st.subheader("2️⃣ Target Job")
    job_description = st.text_area(
        "Paste the job description",
        height=300,
        placeholder=(
            "Paste the complete target job description here...\n\n"
            "Example: Mechanical Engineer – responsibilities, qualifications, "
            "required skills, experience, etc."
        ),
    )

st.divider()

review_button = st.button(
    "🔍 Review Resume",
    type="primary",
    use_container_width=True,
)

if review_button:
    # -----------------------------
    # Input validation
    # -----------------------------
    if not api_key:
        st.error(
            "Please configure GROQ_API_KEY before running the review."
        )
        st.stop()

    if uploaded_pdf is None:
        st.error("Please upload a resume PDF.")
        st.stop()

    if not job_description.strip():
        st.error("Please paste the target job description.")
        st.stop()

    # -----------------------------
    # PDF extraction
    # -----------------------------
    with st.spinner("Reading the resume PDF..."):
        try:
            resume_text = extract_pdf_text(uploaded_pdf)
        except Exception as exc:
            st.error(str(exc))
            st.stop()

    # Keep the request reasonably compact.
    resume_text = clean_text(resume_text, max_chars=30000)
    job_description = clean_text(job_description, max_chars=15000)

    with st.expander("📋 View extracted resume text"):
        st.text(resume_text)

    # -----------------------------
    # AI review
    # -----------------------------
    with st.spinner(
        "CrewAI is reviewing the resume with GPT-OSS 120B..."
    ):
        try:
            start = time.time()
            review = review_with_crewai(
                api_key=api_key,
                resume_text=resume_text,
                job_description=job_description,
            )
            elapsed = time.time() - start

            st.success(f"Review completed in {elapsed:.1f} seconds.")

        except Exception as crew_error:
            # A useful fallback for transient LiteLLM/CrewAI provider issues.
            st.warning(
                "The CrewAI request encountered a provider/framework error. "
                "Trying the direct Groq-compatible API once..."
            )

            try:
                start = time.time()
                review = direct_groq_fallback(
                    api_key=api_key,
                    resume_text=resume_text,
                    job_description=job_description,
                )
                elapsed = time.time() - start
                st.success(
                    f"Review completed using the fallback API in {elapsed:.1f} seconds."
                )

            except Exception as fallback_error:
                st.error(
                    "The review could not be completed.\n\n"
                    f"CrewAI error: {crew_error}\n\n"
                    f"Fallback error: {fallback_error}"
                )
                st.stop()

    # -----------------------------
    # Results
    # -----------------------------
    st.divider()
    st.subheader("📊 Resume Review")
    st.markdown(review)

    st.download_button(
        "⬇️ Download Review as Markdown",
        data=review,
        file_name="resume_review.md",
        mime="text/markdown",
        use_container_width=True,
    )
