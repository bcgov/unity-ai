# Unity AI - Reporting Platform

AI-powered reporting system that converts natural language questions into SQL queries with Metabase visualization integration.

## Quick Start

1. **Clone and navigate:**
```bash
git clone <repository-url>
cd unity-ai/applications
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your Azure OpenAI, JWT, and Metabase credentials
```

3. **Start the application:**
```bash
# Development
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up -d
```

## Services

- **Frontend**: http://localhost:80 - Angular chat interface (container port 8080)
- **Backend**: http://localhost:5000 - Flask API
- **Database**: localhost:5432 - PostgreSQL with pgvector
- **pgAdmin** (dev): http://localhost:8080 - Database admin

## Architecture

- **Backend**: Python Flask + Azure OpenAI + LangChain
- **Frontend**: Angular 20 with BC Government styling
- **Database**: PostgreSQL with pgvector for embeddings
- **Authentication**: JWT with role-based access

## Features

- Natural language to SQL conversion
- AI-powered query explanations
- Chat history and conversation management
- Admin feedback dashboard
- Multi-tenant support
- Metabase card creation and visualization

## Documentation

- [Applications README](./applications/README.md) - Deployment and configuration
- [Backend README](./applications/Unity.AI.Reporting.Backend/README.md) - API documentation
- [Frontend README](./applications/Unity.AI.Reporting.Frontend/README.md) - UI components

## Project Structure

```
unity-ai/
├── applications/
│   ├── Unity.AI.Reporting.Backend/    # Flask API + AI SQL generation
│   ├── Unity.AI.Reporting.Frontend/   # Angular chat interface
│   ├── docker-compose.yml             # Production setup
│   ├── docker-compose.dev.yml         # Development setup
│   └── .env.example                   # Configuration template
├── documentation/                      # Project documentation
└── README.md                          # This file
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE) for details.

## Contributing

This is a BC Government project. For questions or issues, please contact the development team.
