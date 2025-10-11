# api_smoketest.py
import os
from openai import OpenAI
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    organization=os.getenv("OPENAI_ORG_ID") or None,
)

resp = client.responses.create(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    input="Reply with the single word: OK."
)
print(resp.output_text.strip())
