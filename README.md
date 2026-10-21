# Unity AI - Platform

[![Lifecycle:Dormant](https://img.shields.io/badge/Lifecycle-Dormant-ff7f2a)](https://github.com/bcgov/repomountie/blob/master/doc/lifecycle-badges.md)
[![BC Gov Repo](https://img.shields.io/badge/BC_Gov-Unity_AI-blue)](https://github.com/bcgov/Unity/tree/main/applications/Unity.AI)

> This repository has been archived and is read-only. Unity AI has moved into the Unity monorepo at
> [`bcgov/Unity/applications/Unity.AI`](https://github.com/bcgov/Unity/tree/main/applications/Unity.AI),
> where development, pull requests and CI/CD continue. Commit history was carried over, and this
> repository is kept for reference and historical purposes.

## Where Things Moved

| This repository                  | Unity monorepo                                     |
|----------------------------------|----------------------------------------------------|
| `applications/`                  | `applications/Unity.AI/`                           |
| `documentation/`                 | `applications/Unity.AI/documentation/`             |
| `.github/workflows/*.yml`        | `.github/workflows/*-ai.yml`                       |
| SonarCloud `bcgov_unity-ai`      | Unity's combined SonarCloud project                |
| Issues and pull requests         | [bcgov/Unity issues](https://github.com/bcgov/Unity/issues) |

The container images (`<env>-unity-ai-reporting`) and OpenShift statefulsets are unchanged; only the source and pipelines moved.

## Overview

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