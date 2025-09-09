# Unity AI - Reporting AI

A comprehensive AI-powered reporting system that integrates with Metabase to provide intelligent query generation and data insights.

## Features

- AI-powered SQL query generation from natural language
- Integration with Metabase for data visualization
- Real-time chat interface for data queries
- Multi-tenant schema support
- PostgreSQL with pgvector for embeddings storage

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd unity-ai/applications/unity-ai.ReportingAI
```

2. Set required environment variables:
```bash
export OPENAI_API_KEY="your_openai_api_key"
export JWT_SECRET="your_jwt_secret_key"
export METABASE_URL="your_metabase_url"
export METABASE_USERNAME="your_metabase_username"
export METABASE_PASSWORD="your_metabase_password"
```

Or alternatively, copy the environment template:
```bash
cp .env.example .env
# Configure environment variables in .env
```

3. Start development environment:
```bash
docker-compose -f docker-compose.dev.yml up --build
```

### Production Deployment

1. Set required environment variables:
```bash
export OPENAI_API_KEY="your_openai_api_key"
export JWT_SECRET="your_jwt_secret_key"
export METABASE_URL="your_metabase_url"
export METABASE_USERNAME="your_metabase_username"
export METABASE_PASSWORD="your_metabase_password"
```

2. Deploy:
```bash
docker-compose up --build -d
```

## Architecture

- **Backend**: Python Flask API with OpenAI integration
- **Frontend**: Angular application with modern UI
- **Database**: PostgreSQL with pgvector extension
- **Development Tools**: pgAdmin for database management

## Services

- **Frontend**: http://localhost:80
- **Backend API**: http://localhost:5000
- **Database**: localhost:5432
- **pgAdmin** (dev only): http://localhost:8080

## Project Structure

```
applications/unity-ai.ReportingAI/
├── src/
│   ├── unity-ai.ReportingAI.Backend/    # Python Flask backend
│   └── unity-ai.ReportingAI.Frontend/   # Angular frontend
├── docker-compose.yml                   # Production compose
└── docker-compose.dev.yml              # Development compose
```

See individual component READMEs for detailed documentation:
- [Backend Documentation](./src/unity-ai.ReportingAI.Backend/README.md)
- [Frontend Documentation](./src/unity-ai.ReportingAI.Frontend/README.md)