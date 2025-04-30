# clean_and_embed.py

import json
import os
from trafilatura import fetch_url, extract
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

urls = [
  "https://virtourmedia.com/",
  "https://virtourmedia.com/how-it-works/",
  "https://virtourmedia.com/services/",
  "https://agent.virtourmedia.com/order"
]

all_blocks = []
for url in urls:
    html = fetch_url(url)
    text = extract(html) or ""
    all_blocks.append(text)

site_text = "\n\n".join(all_blocks)

# 1) Scrape & clean the main site
#raw_html = fetch_url("https://www.leadspilotai.com")
#site_text = extract(raw_html) or ""

# 2) Break into logical blocks, drop noise
blocks = []
for section in site_text.split("\n\n"):
    text = section.strip()
    if len(text) < 50:                # too short
        continue
    if text.startswith("http") or "@" in text or text.upper() == text:
        continue                     # URLs, emails, all‐caps disclaimers
    blocks.append(text)
cleaned_site = "\n\n".join(blocks)

# 3) Load & clean your JSON FAQs
with open("extra_faqs.json", "r") as f:
    faq_list = json.load(f)

faq_paragraphs = []
for item in faq_list:
    q = item.get("question", "").strip()
    a = item.get("answer", "").strip()
    if len(q) < 10 or len(a) < 20:
        continue
    faq_paragraphs.append(f"Q: {q}\nA: {a}")
cleaned_faqs = "\n\n".join(faq_paragraphs)

# 4) Combine & dedupe lines
combined = cleaned_faqs + "\n\n" + cleaned_site
seen = set()
unique_lines = []
for line in combined.splitlines():
    t = line.strip()
    if not t or t in seen:
        continue
    seen.add(t)
    unique_lines.append(t)
deduped_text = "\n".join(unique_lines)

# 5) Chunk for embeddings
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks   = splitter.split_text(deduped_text)

# 6) Embed & save vectorstore
embeddings  = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(chunks, embeddings)
vectorstore.save_local("virtour_vectorstore")

print(f"✅ Cleaned & embedded {len(chunks)} chunks.")
