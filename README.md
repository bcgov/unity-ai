# Unity AI

A full-stack AI application with Flask backend and Angular frontend for generating SQL queries and visualizations from natural language questions.

## Architecture

- **Backend**: Python Flask API with OpenAI integration and Metabase connectivity
- **Frontend**: Angular application with environment-based configuration
- **Deployment**: Docker containers with nginx proxy

## Quick Start with Docker

### 1. Environment Setup
```bash
cp .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY
# - METABASE_KEY  
# - MB_EMBED_SECRET
```

### 2. Run with Docker Compose
```bash
docker-compose up --build
```

The application will be available at:
- Frontend: http://localhost (port 80)
- Backend API: http://localhost:5000
- PostgreSQL: localhost:5432

### 3. Initialize Schema Embeddings
After first startup, initialize the schema embeddings:
```bash
# Embed schema into PostgreSQL
docker-compose exec backend python main.py g
```

## Development Setup

### Option 1: With PostgreSQL (Recommended)

#### Start PostgreSQL with Docker
```bash
# Start only PostgreSQL service
docker-compose -f docker-compose.dev.yml up -d postgres
```

#### Backend Development
```bash
# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables for PostgreSQL
export USE_POSTGRES=true
export DATABASE_URL=postgresql+psycopg://unity_user:unity_pass@localhost:5432/unity_ai

# Embed schema (run once)
python main.py g

# Start Flask server
python main.py
```

### Option 2: Without PostgreSQL (SQLite)

#### Backend Development
```bash
# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Embed schema (run once)
python main.py g

# Start Flask server
python main.py
```

### Frontend
```bash
cd recap

# Install Angular CLI (once)
npm install -g @angular/cli

# Install dependencies
npm install

# Start development server
ng serve
```

The development setup runs:
- Frontend: http://localhost:4200
- Backend: http://localhost:5000

## Environment Configurations

The frontend supports multiple environment configurations:

- **Development**: `ng serve` - Uses localhost:5000 for API
- **Production**: `ng build --configuration=production` - Uses relative /api paths and nginx proxy

## Docker Services

### PostgreSQL Service
- **Image**: pgvector/pgvector:pg16 (PostgreSQL with vector extension)
- **Port**: 5432
- **Database**: unity_ai
- **User**: unity_user / unity_pass
- **Features**: Vector storage for embeddings, persistent data volume

### Backend Service
- **Base Image**: python:3.11-slim
- **Port**: 5000
- **Environment**: Flask production mode with PostgreSQL
- **Volumes**: Persistent storage for embedded schema
- **Dependencies**: PostgreSQL service

### Frontend Service  
- **Build Stage**: node:22-alpine (Angular build)
- **Runtime Stage**: nginx:alpine (Static file serving)
- **Port**: 80
- **Features**: API proxying, gzip compression, security headers

## API Endpoints

- `POST /api/ask` - Submit natural language questions
- `POST /api/change_display` - Change visualization type
- `DELETE /api/delete/<card_id>` - Delete generated questions

## Features

- Natural language to SQL conversion
- Multiple visualization types (bar, pie, line, map)
- Conversation history
- SQL query inspection
- Metabase integration for data visualization
- JWT-based embedding for secure iframe access

## Configuration

### Required Environment Variables
```
OPENAI_API_KEY=your_openai_api_key_here
METABASE_KEY=your_metabase_api_key_here  
MB_EMBED_SECRET=your_metabase_embed_secret_here
FLASK_ENV=production
```

### Optional Environment Variables
```
MB_URL=https://test-unity-reporting.apps.silver.devops.gov.bc.ca
DB_ID=3
COLLECTION_ID=47

# PostgreSQL Configuration (Docker sets these automatically)
USE_POSTGRES=true
DATABASE_URL=postgresql+psycopg://unity_user:unity_pass@postgres:5432/unity_ai
```

## Troubleshooting

### CORS Issues
The Docker setup uses nginx to proxy API requests, eliminating CORS issues. For development, ensure the backend allows CORS from localhost:4200.

### Schema Embedding
Run `python main.py g` after any database schema changes to re-embed the schema for better query generation.

For Docker: `docker-compose exec backend python main.py g`

### PostgreSQL Connection Issues
If you encounter connection issues with PostgreSQL:

1. **Development**: Ensure PostgreSQL is running: `docker-compose -f docker-compose.dev.yml up -d postgres`
2. **Docker**: Check service health: `docker-compose ps`
3. **Database doesn't exist**: The application will create tables automatically on first run

### Database Migration
To switch between SQLite and PostgreSQL:

1. **To PostgreSQL**: Set `USE_POSTGRES=true` and `DATABASE_URL` in environment
2. **To SQLite**: Set `USE_POSTGRES=false` or remove the variable
3. **Re-embed schema**: Run `python main.py g` after switching databases

### Port Conflicts
- Docker uses ports 80 (frontend) and 5000 (backend)
- Development uses ports 4200 (frontend) and 5000 (backend)
- Modify docker-compose.yml port mappings if needed