# Unity AI

A full-stack AI application with Flask backend and Angular frontend for generating SQL queries and visualizations from natural language questions.

## Quick Start

### 1. Environment Setup
```bash
cp .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY
# - METABASE_KEY  
# - MB_EMBED_SECRET
```

### 2. Production Mode
```bash
docker-compose up --build
```

The application will be available at:
- Frontend: http://localhost (port 80)
- Backend API: http://localhost:5000
- PostgreSQL: localhost:5432

### 3. Development Mode
For development with live reload:
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Development mode features:
- Frontend: Angular dev server with live reload on http://localhost
- Backend: Flask with debug mode and auto-restart on code changes at http://localhost:5000
- Database: PostgreSQL with persistent data

## Generate Schema Embeddings

After first startup, initialize the schema embeddings:
```bash
# Embed schema into PostgreSQL vector store
docker-compose exec backend python main.py g
```

Re-run this command after any database schema changes to update embeddings for better query generation.

## Required Environment Variables
```
OPENAI_API_KEY=your_openai_api_key_here
METABASE_KEY=your_metabase_api_key_here  
MB_EMBED_SECRET=your_metabase_embed_secret_here
```