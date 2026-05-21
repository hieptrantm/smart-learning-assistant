<div align="center">
  <img src="sla2.png" alt="Smart Learning Assistant Logo" width="100%" />
</div>

# Smart Learning Assistant — Personalized AI Learning System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_DB-008CC1?logo=neo4j&logoColor=white)](https://neo4j.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-VectorDB-DC244C)](https://qdrant.tech/)
[![Kong](https://img.shields.io/badge/Kong-API_Gateway-003459?logo=kong&logoColor=white)](https://konghq.com/)

> **Bachelor's Thesis** | University of Engineering and Technology – VNU Hanoi, 2026
>
> **Author:** Tran Van Hiep &nbsp;·&nbsp; **Supervisor:** Dr. Nguyen Van Vinh

---

## Overview

**Smart Learning Assistant** is an end-to-end personalized AI learning assistant built for self-learners. Rather than offering a one-size-fits-all curriculum, the system automatically analyzes user-uploaded academic documents, constructs a Knowledge Graph, generates a study plan tailored to each user's schedule, supports Q&A and tutoring, and **automatically adapts the learning path** based on quiz results.

The system is built on a **microservices** architecture with four core business modules. Agents communicate via the **Model Context Protocol (MCP)**, and **LightRAG** powers dual-level knowledge retrieval from PDF documents.

---

## Demo

<!-- Replace with actual screenshots or video links -->

| Feature | Preview |
|---------|---------|
| Main Interface | ![Demo screenshot](demo.png) |

> 🎬 **Full video demo:** _(Coming soon after deployment)_

---

## Key Features

### 📄 Document Processing & Retrieval Module
- Parses complex PDF documents: text, diagrams, mathematical formulas (LaTeX)
- Bounding-box layout classification; image captioning via **Vision-Language Model**
- Semantic section-based chunking (no arbitrary token cuts)
- Builds a **Knowledge Graph** with rich relations: `PREREQUISITE`, `CAUSES`, `PART_OF`, `DEFINES`…
- Multi-tier indexing: **GraphDB (Neo4j)** + **VectorDB (Qdrant)** (low-level & high-level)
- Multi-tier RAG combining raw chunks, entity profiles, and topic summaries

### 📅 Study Scheduler & Reminder Module
- Auto-generates a study plan based on the user's available time and deadline
- Syncs sessions to **Google Calendar**
- Sends personalized reminder and session-summary emails via **Gmail API**
- Adapts reminder content to the user's actual progress

### 💬 Interactive Learning Support Module
- Explains concepts at the user's current knowledge level
- Multi-turn, document-grounded Q&A (minimizes hallucination)
- Auto-generates quizzes: multiple-choice, short-answer, and practice problems
- Instant feedback with learning history persistence

### 🔄 Adaptive Replanning Module
The system's core differentiator — automatically re-plans the learning path whenever a knowledge gap is detected:

| Strategy | Approach | Strengths | Latency |
|----------|----------|-----------|---------|
| **Tree-based Planning** | Restructures Knowledge Graph into a BFS hierarchy tree | POA ≈ 0.95, ERR ≈ 0 | 90–175s |
| **Sequential Chunk Mapping (SCM)** | Leverages the natural linear order of document chunks | Fast, high RAR | 20–70s |

> Combined strategy: use **Tree-based** for initial path generation and periodic replanning; use **SCM** for real-time quick adjustments.

---

## System Architecture

```
Frontend (React)
        │
        ▼
Kong API Gateway  ←→  Orchestrator LLM
        │
   ┌────┴──────────────────────────┐
   │                               │
Auth Service   Ingest Data    Study Planner   AI Assistant
(Google OAuth)   Service         Service        Service
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                             MCP Server Tools
                    (DocSearch · Gmail · GCalendar · GenQuiz)
                                    │
              ┌─────────────────────┼──────────────────┐
           VectorDB             GraphDB             PostgreSQL
           (Qdrant)             (Neo4j)             (User DB)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, React Router, Google OAuth |
| **Backend** | Python 3.11, FastAPI |
| **API Gateway** | Kong (declarative mode) |
| **AI / RAG** | LightRAG, LLM (OpenAI/compatible), VLM |
| **Agent Protocol** | Model Context Protocol (MCP) |
| **Vector DB** | Qdrant |
| **Graph DB** | Neo4j |
| **Relational DB** | PostgreSQL 15 |
| **Auth** | Google OAuth 2.0 |
| **Integrations** | Google Calendar API, Gmail API |
| **Containerization** | Docker, Docker Compose |

---

## Prerequisites

- **Docker** >= 24.x & **Docker Compose** >= 2.x
- **Node.js** >= 18.x & **npm** >= 9.x (for frontend)
- **Python** >= 3.10 (for local development)
- A Google Cloud project with Calendar API & Gmail API enabled
- An API key for your LLM provider (OpenAI or compatible)

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/hieptrantm/smart-learning-assistant.git
cd smart-learning-assistant
```

### 2. Configure environment variables

Copy the example files and fill in the actual values for each service:

```bash
# From the project root
cp backend/ai-service/env.example        backend/ai-service/.env
cp backend/auth-service/env.example      backend/auth-service/.env
cp backend/data-ingestor/env.example     backend/data-ingestor/.env
cp backend/study-planner-api/env.example backend/study-planner-api/.env
cp backend/mcp-server/env.example        backend/mcp-server/.env

cp frontend/env.example frontend/.env
```

Key variables to configure:

```env
# LLM
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Google OAuth & APIs
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Databases
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/authdb
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=testtest
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

### 3. Start the full stack with Docker

**First-time build and start:**

```bash
cd backend
docker-compose up --build
```

**Start without rebuilding:**

```bash
docker-compose up -d
```

Once running, services are available at:

| Service | URL |
|---------|-----|
| Kong API Gateway | http://localhost:8000 |
| Kong Admin | http://localhost:8004 |
| Auth Service | http://localhost:8001 |
| AI Assistant Service | http://localhost:8002 |
| Data Ingestor | http://localhost:8005 |
| Study Planner | http://localhost:8006 |
| MCP Server | http://localhost:8007 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Neo4j Browser | http://localhost:7474 |

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev       # Development server
npm run build     # Production build
```

The app runs at: **http://localhost:3000**

> **Windows PowerShell:** if you encounter an execution policy error, run this first:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

---

## Hot-reload a Single Service (Development)

Rebuild a specific service without affecting others:

```bash
cd backend

# Rebuild and restart
docker-compose up -d --no-deps --build <service-name>

# Restart only (no rebuild)
docker-compose restart <service-name>
```

Valid service names: `auth-service`, `ai-service`, `data-ingestor`, `study-planner`, `mcp-server`, `kong`

---

## Project Structure

```
smart-learning-assistant/
├── backend/
│   ├── auth-service/        # Google OAuth 2.0 authentication
│   ├── ai-service/          # Tutoring, Q&A, and quiz generation
│   ├── data-ingestor/       # PDF processing & Knowledge Graph builder
│   ├── study-planner-api/   # Study planning & Adaptive Replanning
│   ├── mcp-server/          # MCP tools: DocSearch, Gmail, GCalendar, GenQuiz
│   ├── benchmark/           # Quantitative evaluation notebook
│   ├── db/                  # SQL init schema
│   ├── kong.yml             # Kong API Gateway config
│   └── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   └── pages/
│   └── package.json
└── README.md
```

---

## Benchmark & Evaluation

Quantitative experiments across 5 diverse subjects with 3 metrics:

| Metric | Description | Tree-based | SCM |
|--------|-------------|-----------|-----|
| **POA** (Prerequisite Ordering Accuracy) | Concepts taught in correct prerequisite order | **~0.95** | ~0.88 |
| **RAR** (Relation Activation Rate) | Coverage of key knowledge graph relations | ~0.97 | **~0.99** |
| **ERR** (Entity Redundancy Ratio) | Absence of repeated primary content across sessions | **~0.00** | ~0.12 |
| **Latency** | Planning speed | 90–175s | **20–70s** |

See the full analysis report at [`backend/benchmark/benchmark_analysis_report.ipynb`](backend/benchmark/benchmark_analysis_report.ipynb).

---

## References

- [LightRAG: Simple and Fast Retrieval-Augmented Generation](https://arxiv.org/abs/2410.05779) — Guo et al., 2025
- [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic, 2024
- [GraphMASAL: Graph-based Multi-Agent System for Adaptive Learning](https://arxiv.org/abs/2511.11035) — Zeng et al., 2025

---

## Contributing

Pull requests and issues are welcome. Please follow the commit convention before contributing:

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature-name`
3. Commit: `git commit -m "feat: describe your change"`
4. Push and open a Pull Request

---

## License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for details.

---

<div align="center">

Developed as a **Bachelor's Thesis**
Faculty of Information Technology — University of Engineering and Technology, VNU Hanoi · 2026

</div>
