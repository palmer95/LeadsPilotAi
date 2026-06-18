# clean_and_embed.py

import json
import os
from trafilatura import fetch_url, extract
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()


# CHANGE PER CLIENT
slug = os.getenv("COMPANY_SLUG", "virtour")
faq_path = os.path.join("clients", "faqs", f"{slug}.json")

# CHANGE PER CLIENT
urls = [
    "https://virtourmedia.com/",
    "https://virtourmedia.com/how-it-works/",
    "https://virtourmedia.com/services/",
    "https://virtourmedia.com/industries/",
    "https://agent.virtourmedia.com/order",
]

# ───────────────────────────────────────────────────────────────
# Content filters
# Keep the bot's knowledge base focused on marketing/services info.
# The order page appends VirTour's full legal service agreement after the
# product content, which is useless (and confusing) for a sales bot — so we
# strip it out before anything gets embedded.
# ───────────────────────────────────────────────────────────────

# The agreement is a contiguous trailing block. Truncate each page at the
# first strong "start of contract" marker we find (these are specific enough
# not to appear in normal marketing copy).
LEGAL_START_MARKERS = [
    "1) background",
    "this agreement is between",
    "photography service provider (virtour",
]

def strip_legal_agreement(text: str) -> str:
    lowered = text.lower()
    cut = len(text)
    for marker in LEGAL_START_MARKERS:
        i = lowered.find(marker)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]

# Secondary defense: drop any individual block that still reads as legal
# boilerplate or as leftover order-form UI / confirmation noise.
LEGAL_MARKERS = [
    "this agreement", "service provider", "service fee", "no warranties",
    "warranties", "liability", "liable", "indemnif", "confidential",
    "nonexclusive", "non-exclusive", "perpetual", "licensee", "sublicensee",
    "hereby", "hereafter", "applicable law", "no representations",
    "ownership of photographs", "in exchange for the service", "pre-approved",
    "modification of this agreement",
]
NOISE_MARKERS = [
    "select a photographer", "show all photographers", "please enter the total",
    "may we charge the credit card", "your order has been placed",
    "we could not map this address", "mls number bedrooms",
]

def is_noise(block: str) -> bool:
    t = block.lower()
    return any(m in t for m in LEGAL_MARKERS) or any(m in t for m in NOISE_MARKERS)

# ───────────────────────────────────────────────────────────────
# 1) Scrape & clean the main site (multiple URLs)
# ───────────────────────────────────────────────────────────────
all_blocks = []
for url in urls:
    html = fetch_url(url)
    text = extract(html) or ""
    text = strip_legal_agreement(text)   # drop the contract before it ever gets embedded
    all_blocks.append(text)
site_text = "\n\n".join(all_blocks)

# ───────────────────────────────────────────────────────────────
# 2) Break into logical blocks, drop obvious noise + legal/form junk
# ───────────────────────────────────────────────────────────────
blocks = []
dropped = 0
for section in site_text.split("\n\n"):
    text = section.strip()
    if len(text) < 50:
        continue
    if text.startswith("http") or "@" in text or text.upper() == text:
        continue
    if is_noise(text):
        dropped += 1
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
out_dir = os.path.join("vectorstores", f"{slug}_vectorstore")
vectorstore.save_local(out_dir)

print(f"✅ Cleaned & embedded {len(chunks)} chunks into `{out_dir}` (dropped {dropped} noise/legal blocks).")
