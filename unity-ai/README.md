# Unity AI

A full-stack AI application with Flask backend and Angular frontend for generating SQL queries and visualizations from natural language questions.

## Architecture

- **Backend**: Python Flask API with OpenAI integration and Metabase connectivity
- **Frontend**: Angular application with environment-based configuration and chat history sidebar
- **Database**: PostgreSQL with pgvector extension for vector embeddings
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
# Embed schema into PostgreSQL vector store
docker-compose exec backend python main.py g
```

## Development Setup

### Quick Development Mode (Recommended)
For the fastest development experience with live reload:

```bash
# Start development environment with live reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or just rebuild specific services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build frontend
```

Development mode features:
- **Frontend**: Angular dev server with live reload on http://localhost
- **Backend**: Flask with debug mode and auto-restart on code changes at http://localhost:5000
- **Database**: PostgreSQL with persistent data
- **Live Reload**: Changes to source files trigger automatic rebuilds
- **Debug Mode**: Detailed error pages and verbose logging

### Manual Development Setup

#### Backend Development (PostgreSQL Required)

##### Start PostgreSQL with Docker
```bash
# Start only PostgreSQL service
docker-compose -f docker-compose.yml up -d postgres
```

##### Backend Development
```bash
# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables for PostgreSQL
export DATABASE_URL=postgresql+psycopg://unity_user:unity_pass@localhost:5432/unity_ai

# Embed schema (run once)
python main.py g

# Start Flask server
python main.py
```

#### Frontend Development (Manual)
```bash
cd recap

# Install Angular CLI (once)
npm install -g @angular/cli

# Install dependencies
npm install

# Start development server
ng serve
```

Manual development setup runs:
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
- **Environment**: Flask with configurable debug mode (controlled by FLASK_ENV)
- **Dependencies**: PostgreSQL service with pgvector extension
- **Production**: `FLASK_ENV=production` - optimized performance, no debug
- **Development**: `FLASK_ENV=development` - debug mode, auto-reload

### Frontend Service  
- **Build Stage**: node:22-alpine (Angular build)
- **Runtime Stage**: nginx:alpine (Static file serving)
- **Port**: 80
- **Features**: API proxying, gzip compression, security headers

## API Endpoints

- `POST /api/ask` - Submit natural language questions
- `POST /api/change_display` - Change visualization type
- `DELETE /api/delete/<card_id>` - Delete generated questions
- `POST /api/chats` - Get all user chats
- `POST /api/chats/{id}` - Load specific chat conversation
- `POST /api/chats/save` - Save/update chat conversation
- `DELETE /api/chats/{id}` - Delete a chat

## Features

- Natural language to SQL conversion
- Multiple visualization types (bar, pie, line, map)
- Toggle-able sidebar with chat history
- Persistent conversation storage
- SQL query inspection
- Metabase integration for data visualization
- JWT-based embedding for secure iframe access

## Configuration

### Required Environment Variables
```
OPENAI_API_KEY=your_openai_api_key_here
METABASE_KEY=your_metabase_api_key_here  
MB_EMBED_SECRET=your_metabase_embed_secret_here
```

### Optional Environment Variables
```
# Flask Environment (controls debug mode and performance)
FLASK_ENV=production          # Use 'production' for optimized performance, 'development' for debugging

# PostgreSQL Configuration (Docker sets these automatically)
DATABASE_URL=postgresql+psycopg://unity_user:unity_pass@postgres:5432/unity_ai
DB_HOST=postgres
DB_PORT=5432
DB_NAME=unity_ai
DB_USER=unity_user
DB_PASSWORD=unity_pass
```

## Troubleshooting

### CORS Issues
The Docker setup uses nginx to proxy API requests, eliminating CORS issues. For development, ensure the backend allows CORS from localhost:4200.

### Schema Embedding
Run `python main.py g` after any database schema changes to re-embed the schema for better query generation. This stores vector embeddings in PostgreSQL using the pgvector extension.

For Docker: `docker-compose exec backend python main.py g`

### PostgreSQL Connection Issues
If you encounter connection issues with PostgreSQL:

1. **Development**: Ensure PostgreSQL is running: `docker-compose -f docker-compose.dev.yml up -d postgres`
2. **Docker**: Check service health: `docker-compose ps`
3. **Database doesn't exist**: The application will create tables automatically on first run
4. **pgvector extension**: Ensure the pgvector extension is installed (included in pgvector/pgvector:pg16 image)

### Database Requirements
The application now requires PostgreSQL with the pgvector extension for vector embeddings storage. 

### Port Conflicts
- Docker uses ports 80 (frontend) and 5000 (backend)
- Development uses ports 4200 (frontend) and 5000 (backend)
- Modify docker-compose.yml port mappings if needed