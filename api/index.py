from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import Optional
from io import BytesIO

try:
    from PyPDF2 import PdfReader  # type: ignore[import-not-found]
except Exception:
    PdfReader = None

try:
    import pandas as pd  # type: ignore[import-not-found]
except Exception:
    pd = None

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <h2>🔥 Hot Mess Coach</h2>
    <form action="/chat" method="post" enctype="multipart/form-data">
        <p>Your message:</p>
        <textarea name="user_message" rows="4" cols="50">I feel like a hot mess today...</textarea><br><br>
        <p>Optional document (PDF or CSV) to include as context:</p>
        <input type="file" name="doc" accept=".pdf,.csv" /><br><br>
        <button type="submit">Coach me</button>
    </form>
    """

@app.post("/chat", response_class=HTMLResponse)
def chat(
    user_message: str = Form(...),
    doc: Optional[UploadFile] = File(None),
):
    # Extract optional uploaded content
    uploaded_content: Optional[str] = None
    try:
        if doc is not None and doc.filename:
            filename = (doc.filename or "").lower()
            content_type = (doc.content_type or "").lower()
            # Read all bytes once
            raw_bytes = doc.file.read()
            if (filename.endswith(".csv") or "text/csv" in content_type):
                if pd is not None:
                    try:
                        # Use pandas if available for a clean table-to-string
                        import io
                        df = pd.read_csv(io.BytesIO(raw_bytes))
                        uploaded_content = df.to_string()
                    except Exception:
                        # Fallback: decode
                        uploaded_content = raw_bytes.decode("utf-8", errors="ignore")
                else:
                    uploaded_content = raw_bytes.decode("utf-8", errors="ignore")
            elif (filename.endswith(".pdf") or "application/pdf" in content_type):
                if PdfReader is not None:
                    try:
                        reader = PdfReader(BytesIO(raw_bytes))
                        text_parts = []
                        for page in getattr(reader, "pages", []):
                            page_text = page.extract_text() or ""
                            text_parts.append(page_text)
                        uploaded_content = "\n".join(text_parts)
                    except Exception as e:
                        uploaded_content = f"[PDF extraction error]: {e}"
                else:
                    uploaded_content = "[PDF uploaded but PyPDF2 is not installed. Run: pip install PyPDF2]"
            else:
                # Unknown type: try to decode as text
                try:
                    uploaded_content = raw_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    uploaded_content = None
    except Exception:
        uploaded_content = None

    # Truncate to protect prompt size
    if uploaded_content:
        uploaded_content = uploaded_content[:8000]

    system_prompt = "You are a supportive mental coach who helps overwhelmed people feel calmer."
    if uploaded_content:
        system_prompt += "\n\nThe user has also uploaded a document. Here is the content:\n" + uploaded_content

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    )

    coach_reply = response.choices[0].message.content

    return f"""
    <h2>🔥 Hot Mess Coach Says</h2>
    <div style="white-space: pre-wrap; border: 1px solid #ccc; padding: 12px; border-radius: 8px;">
        {coach_reply}
    </div>
    {"<p><i>Document context was included.</i></p>" if uploaded_content else ""}
    <br><a href="/">⬅ Back</a>
    """

#uvicorn backend.test_llm:app --reload --host 0.0.0.0 --port 8000