# Effision — Enterprise Product Brain & Semantic Vector PIM

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E.svg)](https://supabase.com/)
[![Groq](https://img.shields.io/badge/Groq-AI%20Enrichment-F55036.svg)](https://groq.com/)
[![SentenceTransformers](https://img.shields.io/badge/SentenceTransformers-all--MiniLM--L6--v2-orange.svg)](https://www.sbert.net/)
[![UI Style](https://img.shields.io/badge/Design-Apple%20Aesthetic-white.svg)](#-apple-inspired-pim-web-ui)

**Effision** is an intelligent Product Information Management (PIM), Vector Database, and Knowledge Graph system designed for complex industrial procurement catalogs and supplier spec sheets.

</div>

---

## 🌟 Key Features

* 🚀 **Multi-Format Ingestion Engine**: Seamlessly processes structured procurement CSVs/Excel catalogs and unstructured spec sheets (PDF, Word, Text) via **LlamaParse** and **Pandas**.
* 🧠 **AI-Powered PIM Enrichment**: Employs **Groq LLMs** (`openai/gpt-oss-120b`) to normalize fragmented brands, craft SEO-ready titles, generate punchy value propositions, extract technical specifications, and categorize products.
* ⚡ **Dense Vector Embeddings & Semantic Search**: Generates local 384-dimensional dense vectors with `all-MiniLM-L6-v2` and indexes them in **Supabase PostgreSQL** via **`pgvector`** with HNSW cosine distance indexing (`match_documents` RPC).
* 🛡️ **Human-in-the-Loop Provenance Graph**: Enforces a strict **propose-only rule** — all AI-extracted relationships and specs carry confidence scores and citations, remaining in `"proposed"` status until approved by a product manager.
* 🍎 **Apple-Inspired PIM Web Application**: Built with **Instrument Serif** and **Instrument Sans** typography, frosted titanium glassmorphism (`backdrop-filter: blur(30px)`), bento metrics, slide-over spec inspector, and `⌘K` command palette.

---

## 🏗️ System Architecture & Data Flow

```
                      ┌────────────────────────────────────────┐
                      │            RAW INPUT SOURCES           │
                      │  - Industrial CSVs (Procurement data)  │
                      │  - PDFs / Word Spec Sheets             │
                      │  - Plain Text / Markdown               │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    LAYER 1: PARSING & EXTRACTION       │
                      │  - LlamaParse (PDF / DOCX)             │
                      │  - Pandas Engine (Structured CSVs)     │
                      │  - Offline Strategy (.txt / .md)       │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    LAYER 2: AI ENRICHMENT (Groq)       │
                      │  - Normalizes brands & part numbers    │
                      │  - Generates SEO titles & summaries    │
                      │  - Extracts specs, features & keywords │
                      └───────────────────┬────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
      ┌───────────────────────────┐               ┌───────────────────────────┐
      │  LAYER 3A: VECTOR DB      │               │  LAYER 3B: KNOWLEDGE GRAPH│
      │  (Supabase + pgvector)    │               │  (Nodes & Edges Engine)   │
      ├───────────────────────────┤               ├───────────────────────────┤
      │ • all-MiniLM-L6-v2 Embed  │               │ • Product, Attribute,     │
      │ • 384-dim Dense Vectors   │               │   Category, Supplier      │
      │ • HNSW Cosine Index       │               │ • Proposed status + conf. │
      │ • Semantic Search RPC     │               │ • Full document provenance│
      └─────────────┬─────────────┘               └─────────────┬─────────────┘
                    │                                           │
                    └─────────────────────┬─────────────────────┘
                                          ▼
                      ┌────────────────────────────────────────┐
                      │       LAYER 4: FASTAPI & SERVICES      │
                      │  • GET /graph (Interactive Graph View) │
                      │  • GET /review/queue (Pending Edges)   │
                      │  • POST /review/{id}/decision          │
                      │  • Semantic Search & Audit Reports     │
                      └────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
Effision/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_graph.py        # Graph visualization API
│   │   │   ├── routes_review.py       # Human-in-the-loop review governance
│   │   │   └── routes_products.py     # PIM catalog, stats, & vector search API
│   │   ├── db/
│   │   │   ├── schema.sql             # PostgreSQL pgvector & HNSW schema
│   │   │   ├── supabase_client.py     # Supabase client & local SQLite shim
│   │   │   └── vector_service.py      # Core embedding & vector search service
│   │   ├── explain/
│   │   │   └── report.py              # PDF audit report generator (WeasyPrint)
│   │   ├── models/
│   │   │   └── schema.py              # Pydantic schemas (EnrichedProduct, Nodes, Edges)
│   │   ├── pipeline/
│   │   │   ├── ingestor.py            # Unified parser (PDF/DOCX/CSV/TXT)
│   │   │   ├── segregate.py           # LLM attribute extraction
│   │   │   └── graph_model.py         # Knowledge graph node & edge persister
│   │   └── main.py                    # FastAPI application entry point & static server
│   ├── frontend/
│   │   ├── index.html                 # Apple-style PIM single-page application
│   │   ├── style.css                  # Frosted titanium glassmorphism & typography
│   │   └── app.js                     # Vector search, drawer inspector, & graph canvas
│   ├── scripts/
│   │   ├── ingest_unihack_csv.py      # Batch procurement CSV to Supabase pipeline
│   │   ├── query_vector_db.py         # CLI tool to list, query, & insert vector rows
│   │   ├── view_supabase.py           # Terminal viewer for Supabase vector records
│   │   └── run_pipeline.py            # Document pipeline runner for spec sheets
│   ├── Unihack_ Sample.csv            # Industrial procurement dataset (1,000 items)
│   ├── requirements.txt               # Python package dependencies
│   └── .env                           # API keys & Supabase credentials
├── Annual_Procurement_Report.pdf      # Sample procurement spec document
└── README.md
```

---

## ⚙️ Prerequisites & Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/wehaveaguru/Effision.git
cd Effision/backend

# Create & activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or edit `backend/.env`:

```env
GROQ_API_KEY=gsk_your_groq_api_key
LLAMA_CLOUD_API_KEY=llx-your_llama_cloud_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_or_service_role_key
```

---

## 🚀 Running the Project

### 1. Launch the PIM Web Application

Start the FastAPI backend server (which automatically hosts the static PIM web app):

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🖥️ Apple-Inspired PIM Web UI

The frontend interface incorporates Apple's Human Interface Guidelines (HIG):

* **Catalog Explorer**: Bento dashboard metrics, brand filtering pills (Diablo, 3M, Mirka), and responsive card grids.
* **Slide-Over Product Inspector**: Shows the core value proposition quote, enriched specifications table, verified feature checklist, search keyword tags, and an interactive 384-dimensional vector fingerprint sparkline.
* **Neural Vector Search Studio**: Execute natural language queries with real-time cosine distance similarity percentages.
* **Review Queue**: Human-in-the-loop governance interface to approve or reject AI-proposed specifications.
* **Knowledge Graph Explorer**: Interactive canvas rendering relationships between Products, Brands, Categories, and Specs.
* **Global Command Palette (`⌘K` / `Ctrl+K`)**: Quick vector search from anywhere in the app.

---

## 📄 License & Attribution

Built for **Unihacks Hackathon** by **Team Effision**. Distributed under the MIT License.
