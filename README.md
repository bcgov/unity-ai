# Unity AI - Platform

AI-powered  

- Reporting system that converts natural language questions into SQL queries with Metabase integration.
- Application assessment system allowing for autonomous background application review and scoring.

## Quick Start

1. **Navigate to applications directory:**
```bash
cd applications
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your Azure OpenAI, JWT, and Metabase credentials
```

3. **Start the application:**
```bash
docker-compose up --build
```

4. **Access the application:**
   - Application: http://localhost
   - Testing with JWT: http://localhost/?token=YOUR_JWT_TOKEN

## Architecture

**Single Combined Container**: Flask serves both the Angular frontend (static files) and backend API endpoints.

```
Browser (localhost:80) → Flask (container port 8080)
                          ├── /api/* → Backend API
                          └── /*     → Angular static files
```

## Key Features

- **AI Query Generation**: Natural language to SQL conversion using Azure OpenAI
- **Smart Authentication**: JWT with hybrid local/production modes (URL tokens for localhost, PostMessage for production)
- **Origin Security**: ORIGIN_URL environment variable for iframe origin validation
- **Chat Management**: Conversation history and AI-powered SQL explanations
- **Admin Dashboard**: Feedback collection and administrative controls
- **Multi-tenant**: Configurable database mappings and tenant isolation
- **Vector Search**: PostgreSQL with pgvector for intelligent schema embeddings

## Project Structure

```
unity-ai/
├── applications/
│   ├── Unity.AI.Reporting.Backend/    # Flask API + AI SQL generation
│   ├── Unity.AI.Reporting.Frontend/   # Angular chat interface
│   ├── Dockerfile                     # Combined frontend+backend build
│   ├── docker-compose.yml             # Local development setup
│   ├── .env.example                   # Configuration template
│   └── README.md                      # Deployment guide
├── documentation/                      # Project documentation
└── .github/workflows/                 # CI/CD pipelines
```

## Documentation

- [Applications README](./applications/README.md) - Detailed setup and deployment
- [Environment Configuration](./applications/documentation/environment-specific-configuration.md) - Environment variables guide
- [Manual Deployment Guide](./documentation/manual-image-build-push-openshift.md) - OpenShift deployment

## Tech Stack

- **Frontend**: Angular 20, Material UI, PrimeNG
- **Backend**: Flask, Azure OpenAI, LangChain, PGVector  
- **Database**: PostgreSQL 16 with pgvector extension
- **Container**: Docker (multi-stage build, OpenShift compatible)

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE) for details.

## Contributing

This is a BC Government project. For questions or issues, please contact the development team.