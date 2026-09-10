# Unity AI - Platform

[![Lifecycle:Stable](https://img.shields.io/badge/Lifecycle-Stable-97ca00)](https://github.com/bcgov/repomountie/blob/master/doc/lifecycle-badges.md)

OpenAI-powered  

- Reporting system that converts natural language questions into SQL queries with Metabase integration.
- Application assessment system allowing for autonomous background application review and scoring.

## Directory Structure

    .github/workflows/           - CI/CD pipelines
    applications/                - Application root (frontend, backend, Docker)
    documentation/                - Project documentation
    COMPLIANCE.yaml               - BCGov PIA/STRA compliance status
    CONTRIBUTING.md               - How to contribute
    LICENSE                       - License
    SECURITY.md                   - Security Policy and Reporting

## Key Features

- **AI Query Generation**: Natural language to SQL conversion using Azure OpenAI
- **Smart Authentication**: JWT with hybrid local/production modes (URL tokens for localhost, PostMessage for production)
- **Origin Security**: ORIGIN_URL environment variable for iframe origin validation
- **Chat Management**: Conversation history and AI-powered SQL explanations
- **Admin Dashboard**: Feedback collection and administrative controls
- **Multi-tenant**: Configurable database mappings and tenant isolation
- **Vector Search**: PostgreSQL with pgvector for intelligent schema embeddings

## Documentation

- [Applications README](./applications/README.md) - Detailed setup and deployment
- [Quick Start & Architecture](./documentation/unity-ai-reporting-quick-start.md) - Local setup and container architecture
- [Environment Configuration](./documentation/unity-ai-reporting-environment-specific-configuration.md) - Environment variables guide
- [Manual Deployment Guide](./documentation/manual-image-build-push-openshift.md) - OpenShift deployment

## Technology

- **Frontend**: Angular, TypeScript, Vitest
- **Backend**: Flask (Python), Azure OpenAI, LangChain, pgvector
- **Database**: PostgreSQL with pgvector extension
- **Container**: Docker (multi-stage build, OpenShift compatible)

## License

Licensed under the MIT License. See [LICENSE](./LICENSE) for details.