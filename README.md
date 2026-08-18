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

### 3. Initialize Supabase Vector Database

Run [`backend/app/db/schema.sql`](backend/app/db/schema.sql) in your **Supabase SQL Editor**:

```sql
-- 1. Enable pgvector extension
create extension if not exists vector;

-- 2. Create documents table with 384 dimensions
create table if not exists documents (
    id bigint primary key generated always as identity,
    content text not null,
    metadata jsonb default '{}'::jsonb,
    embedding vector(384)
);

-- 3. Create HNSW index for ultra-fast cosine similarity search
create index if not exists documents_embedding_hnsw_idx 
on documents using hnsw (embedding vector_cosine_ops);

-- 4. Disable RLS or add permissive policies for API access
alter table documents disable row level security;

-- 5. Create match_documents RPC
create or replace function match_documents (
  query_embedding vector(384),
  match_threshold float default 0.3,
  match_count int default 5
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;
```

---

## 🚀 Running the Project

### 1. Ingest Products into Supabase Vector DB

Ingest the industrial catalog with Groq AI enrichment and local vector embedding:

```bash
# Ingest entire 1,000-row catalog
python -X utf8 scripts/ingest_unihack_csv.py

# Ingest first 20 rows for quick testing
python -X utf8 scripts/ingest_unihack_csv.py --limit 20

# Dry-run test (no database writes)
python -X utf8 scripts/ingest_unihack_csv.py --limit 5 --dry-run
```

### 2. Query the Vector Database via CLI

```bash
# 1. List all rows in Supabase
python -X utf8 scripts/query_vector_db.py --list

# 2. Test semantic search with natural language
python -X utf8 scripts/query_vector_db.py --query "sanding belt for metal and wood"
python -X utf8 scripts/query_vector_db.py --query "3M cubitron grinding disc P120" --top-k 3

# 3. Insert custom test product directly
python -X utf8 scripts/query_vector_db.py --insert-test "Bosch 18V Cordless Drill with Brushless Motor" --title "Bosch 18V Drill" --brand "Bosch"
```

### 3. Launch the PIM Web Application

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

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/products` | List enriched products from Supabase with pagination & brand filters |
| `GET` | `/api/products/stats` | Retrieve PIM catalog metrics (total products, brands, accuracy) |
| `POST` | `/api/products/search` | Execute vector semantic search using cosine similarity |
| `POST` | `/api/products/insert` | Embed & insert a new enriched product into Supabase |
| `GET` | `/graph?status=approved` | Retrieve nodes and edges for knowledge graph visualization |
| `GET` | `/edges/queue` | List AI-proposed attributes awaiting human review |
| `POST` | `/edges/{id}/review` | Approve or reject a proposed edge with reviewer attribution |
| `GET` | `/health` | API health check endpoint |

---

## 📄 License & Attribution

Built for **Unihacks Hackathon** by **Team Effision**. Distributed under the MIT License.
