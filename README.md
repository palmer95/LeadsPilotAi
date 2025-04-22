# 🧠 Leads Pilot AI 

**The AI Sales Agent That Works While You Sleep**

PromptlyAI is a fully branded, AI-powered chatbot that installs on any website and turns visitors into leads — and leads into bookings. Custom-built per client, it engages in real-time, answers customer questions, and books jobs automatically.

---

## 🔧 Built For

- Real estate media companies
- Home service providers
- Agencies with high inbound interest
- Any business that needs fast, intelligent response on their website

---

## ⚙️ Features

### ✅ Core Capabilities
- **Contextual Q&A** powered by OpenAI + LangChain
- **Vector-based memory** using FAISS for ultra-fast, accurate answers
- **GPT fallback** when custom site data isn’t enough
- **Conversation memory** for smooth follow-up questions
- **Instant reset** to clear chat history

### 🎨 Customization & Branding
- Client-specific logo and color theming
- Static brand context for GPT tone/pitch alignment
- Custom CSS support (per-client)

### 📦 Delivery & Installation
- Installs via a single `<script>` tag
- Lightweight, fast-loading React UI
- Backend served via Flask

### 🔌 Optional Add-ons (Coming Soon)
- Auto-booking integration (Calendly, native form, or API)
- SMS or Discord notifications on booking confirmation
- Per-client admin dashboard with usage/fallback stats
- FAQ button injection for guided experiences

---

## 🚀 How It Works (MVP Flow)

1. **Ingest Client Website**  
   Scrapes key pages like `/services`, `/about`, `/contact`  
2. **Embed + Store Context**  
   Text is chunked, embedded, and stored in FAISS
3. **Serve via API**  
   Flask backend handles chat requests and invokes LangChain
4. **React Frontend**  
   User chat is handled in a modern interface with memory, loading state, FAQ buttons, and branding
5. **Deploy**  
   Client adds one line of code to their site to embed the bot

---

## 🛠️ Tech Stack

- **Frontend**: React + Vite (UI)
- **Backend**: Flask + LangChain + OpenAI
- **Vectorstore**: FAISS
- **Styling**: Custom CSS per client
- **Hosting**: Vercel (frontend) + Render (backend)

---

## 👥 Team & Credits

**Built by:** [@palmer95](https://github.com/palmer95)  
**Sales Partner & First Client:** [Virtour Media](https://virtourmedia.com)  
**Logo/Branding/Marketing Support:** [LeadsPilotAi Marketing Team (WIP)]  

---

## 🔐 Status

This is an **early-stage private MVP**, actively in development.  
🚧 Features are being added daily.  
🛠️ Internal use only — please do not share without permission.

---

## 📬 Want to use LeadsPilotAi on your website?

We're currently onboarding early clients.  
Email us at **hello@leadspilotai.com** or join the waitlist [coming soon].

