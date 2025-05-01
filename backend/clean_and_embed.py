# clean_and_embed.py

import json
import os
from trafilatura import fetch_url, extract
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()


# CHANGE PER CLIENT
slug = os.getenv("COMPANY_SLUG", "leadspilotai")
faq_path = os.path.join("clients", "faqs", f"{slug}.json")

# ───────────────────────────────────────────────────────────────
# 1) Scrape & clean the main site (multiple URLs)
# ───────────────────────────────────────────────────────────────

# CHANGE PER CLIENT
urls = [
    "https://www.leadspilotai.com/",
    "https://www.leadspilotai.com/product",
    "https://www.leadspilotai.com/pricing",
]
all_blocks = []
for url in urls:
    html = fetch_url(url)
    text = extract(html) or ""
    all_blocks.append(text)
site_text = "\n\n".join(all_blocks)

# ───────────────────────────────────────────────────────────────
# 2) Break into logical blocks, drop obvious noise
# ───────────────────────────────────────────────────────────────
blocks = []
for section in site_text.split("\n\n"):
    text = section.strip()
    if len(text) < 50:
        continue
    if text.startswith("http") or "@" in text or text.upper() == text:
        continue
    blocks.append(text)
cleaned_site = "\n\n".join(blocks)

# ───────────────────────────────────────────────────────────────
# 3) Optionally load & format per-client FAQs
# ───────────────────────────────────────────────────────────────
faq_paragraphs = []
if os.path.isfile(faq_path):
    try:
        with open(faq_path, "r") as f:
            faq_list = json.load(f)
        for item in faq_list:
            q = item.get("question", "").strip()
            a = item.get("answer", "").strip()
            # skip too-short entries
            if len(q) < 10 or len(a) < 20:
                continue
            faq_paragraphs.append(f"Q: {q}\nA: {a}")
    except Exception as e:
        print(f"⚠️ Failed to load {faq_path}: {e}")

cleaned_faqs = "\n\n".join(faq_paragraphs)

# ───────────────────────────────────────────────────────────────
# 4) Combine FAQs + site content, dedupe lines
# ───────────────────────────────────────────────────────────────
if cleaned_faqs:
    combined = cleaned_faqs + "\n\n" + cleaned_site
else:
    combined = cleaned_site

seen = set()
unique_lines = []
for line in combined.splitlines():
    t = line.strip()
    if not t or t in seen:
        continue
    seen.add(t)
    unique_lines.append(t)

deduped_text = "\n".join(unique_lines)

# ───────────────────────────────────────────────────────────────
# 5) Chunk for embeddings
# ───────────────────────────────────────────────────────────────
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks   = splitter.split_text(deduped_text)

# ───────────────────────────────────────────────────────────────
# 6) Embed & save vectorstore
# ───────────────────────────────────────────────────────────────
embeddings  = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(chunks, embeddings)

# save under a client‐specific name
out_dir = f"{slug}_vectorstore"
vectorstore.save_local(out_dir)

print(f"✅ Cleaned & embedded {len(chunks)} chunks into `{out_dir}`.")
