# Unity AI - Reporting Platform

AI-powered reporting system that converts natural language questions into SQL queries with Metabase integration.

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

## Architecture

**Single Combined Container**: Flask serves both the Angular frontend (static files) and backend API endpoints.

```
Browser (localhost:80) → Flask (container port 8080)
                          ├── /api/* → Backend API
                          └── /*     → Angular static files
```

## Key Features

- Natural language to SQL conversion using Azure OpenAI
- AI-powered query explanations
- Chat history and conversation management  
- Admin feedback dashboard
- Multi-tenant support with configurable database mappings
- JWT authentication with role-based access
- PostgreSQL with pgvector for schema embeddings

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