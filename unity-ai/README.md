# Metabase Reporter

A modular, extensible natural language to SQL application integrated with Metabase. Convert natural language queries into SQL, create visualizations, and manage conversations with multi-tenant support.

## Features

- 🤖 **Natural Language to SQL**: Convert plain English questions into SQL queries
- 📊 **Metabase Integration**: Automatic card creation and visualization
- 🏢 **Multi-Tenant Support**: Database isolation per tenant with db_id filtering
- 💬 **Conversation Management**: Save and restore chat histories
- 🔍 **Smart Schema Search**: Vector embeddings for relevant table discovery
- 🎯 **Majority Voting**: Multiple LLM samples for robust SQL generation
- 🔌 **Extensible Architecture**: Modular design for easy customization

## Project Structure

```
unity-ai/
├── backend/                    # Modular Python backend
│   ├── config.py              # Configuration management
│   ├── database.py            # Database operations
│   ├── metabase.py            # Metabase API client
│   ├── embeddings.py          # Vector embeddings
│   ├── chat.py                # Chat management
│   ├── sql_generator.py       # NL to SQL conversion
│   ├── api.py                 # Flask API routes
│   ├── app.py                 # Main entry point
│   ├── requirements.txt       # Backend dependencies
│   └── QDECOMP_examples.json  # Few-shot examples
├── frontend/                   # Angular frontend
│   ├── src/                   # Angular source code
│   ├── Dockerfile             # Frontend production build
│   ├── Dockerfile.dev         # Frontend development build
│   ├── nginx.conf             # Nginx configuration
│   ├── package.json           # Frontend dependencies
│   └── angular.json           # Angular configuration
├── main.py                     # Legacy monolithic backend (kept for compatibility)
├── custom_fields.py           # Custom field utilities
├── daily_job.py               # Scheduled tasks
├── docker-compose.yml         # Production orchestration
├── docker-compose.dev.yml     # Development orchestration
├── Dockerfile                 # Backend container definition
├── QDECOMP_examples.json      # NL-to-SQL training examples
├── sql_examples.json          # Additional SQL examples
└── README.md                  # This file
```

## Quick Start

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd unity-ai
```

2. **Set up environment variables**
```bash
# Create .env file in parent directory (outside project for security)
cp ../.env.example ../.env
# Edit ../.env with your configuration
```

3. **Install dependencies**
```bash
cd backend
pip install -r backend/requirements.txt
```

4. **Initialize database**
```bash
python app.py
# The database tables will be created automatically
```

5. **Embed database schemas**
```bash
python app.py embed
# Or for a specific database:
python app.py embed 3
```

### Docker Deployment

#### Production
```bash
# Build and run all services (backend, frontend, database)
docker-compose --env-file ../.env up --build

# Embed schemas in the backend container
docker-compose --env-file ../.env exec backend python app.py embed
```

#### Development
```bash
# Run with development configuration (hot reload, pgAdmin)
docker-compose --env-file ../.env -f docker-compose.dev.yml up --build

# If you encounter dependency issues, force rebuild without cache:
docker-compose --env-file ../.env -f docker-compose.dev.yml build --no-cache
docker-compose --env-file ../.env -f docker-compose.dev.yml up

# Access services:
# - Frontend: http://localhost
# - Backend: http://localhost:5000
# - pgAdmin: http://localhost:8080 (admin@example.com / admin)
```

## Configuration

### Environment Variables

Create a `.env` file in the parent directory (`../`) for security:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=unity_ai
DB_USER=unity_user
DB_PASSWORD=unity_pass

# Metabase Configuration
MB_EMBED_URL=https://your-metabase-instance.com
METABASE_KEY=your-metabase-api-key
MB_EMBED_SECRET=your-embed-secret

# AI Configuration
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_API_VERSION=2024-02-01
```

### Tenant Configuration

Add new tenants in `backend/config.py`:

```python
def _load_tenant_mappings(self):
    return {
        "YourOrg": {
            "db_id": 5,
            "collection_id": 100,
            "schema_types": ["public", "custom"]
        }
    }
```

## API Endpoints

### Query Processing
- `POST /api/ask` - Convert natural language to SQL and create Metabase card
  ```json
  {
    "question": "How many users signed up last month?",
    "conversation": [],
    "metabase_url": "https://metabase.example.com",
    "tenant_id": "YourOrg"
  }
  ```

### Visualization Management
- `POST /api/change_display` - Update card visualization type
- `POST /api/delete` - Delete a Metabase card

### Chat Management
- `POST /api/chats` - Get all chats for a user
- `POST /api/chats/<id>` - Get specific chat with card validation
- `POST /api/chats/save` - Save or update chat
- `DELETE /api/chats/<id>` - Delete chat

## CLI Commands

### Backend Commands (from project root)
```bash
# Run the modular Flask server
python backend/app.py

# Embed database schemas
python backend/app.py embed [db_id]

# Show help
python backend/app.py help

# Legacy backend (main.py - for compatibility)
python main.py
python main.py g [db_id]  # embed schemas
```

### Frontend Development (from frontend/ directory)
```bash
cd frontend
npm install
npm start      # Development server
npm run build  # Production build
```

## Extending the Application

### Adding New Use Cases

1. **Configure the tenant** in `backend/config.py`
2. **Customize schema extraction** in `backend/embeddings.py`
3. **Add domain-specific examples** to `QDECOMP_examples.json`
4. **Extend API endpoints** in `backend/api.py`

### Replacing Components

The modular architecture allows easy replacement of:
- **LLM Provider**: Modify `sql_generator.py`
- **BI Tool**: Replace `metabase.py` with your BI tool's API
- **Database**: Update `database.py` for different backends
- **Embeddings**: Change vector store in `embeddings.py`

## Development

### Running Tests
```bash
cd backend
python -m pytest tests/
```

### Code Structure

Each module is independent and focused:
- `config.py` - All configuration in one place
- `database.py` - Database operations only
- `metabase.py` - Metabase API interactions
- `embeddings.py` - Vector operations
- `chat.py` - Conversation logic
- `sql_generator.py` - NL to SQL logic
- `api.py` - HTTP endpoints
- `app.py` - Application bootstrap

## Production Deployment

### Using Docker

The application includes both backend and frontend containers:

```bash
# Production deployment
docker-compose --env-file ../.env up --build -d

# Backend only (for API development)
docker build -t metabase-reporter-backend .
docker run -p 5000:5000 --env-file ../.env metabase-reporter-backend

# Development with hot reload
docker-compose --env-file ../.env -f docker-compose.dev.yml up --build
```

### Health Checks

- Health endpoint: `GET /`
- Returns: "Backend is working!"

### Scaling Considerations

- Use PostgreSQL connection pooling
- Deploy multiple Flask workers with Gunicorn
- Cache embeddings for frequently accessed schemas
- Use Redis for session management (if needed)

## Troubleshooting

### Common Issues

1. **Environment variables not loaded**
   - Ensure `.env` file is in parent directory (`../`)
   - Check that docker-compose files reference `../.env` correctly
   - Verify all required environment variables are set

2. **Module import errors (e.g., "ModuleNotFoundError: No module named 'dotenv'")**
   - Force rebuild without cache: `docker-compose --env-file ../.env -f docker-compose.dev.yml build --no-cache`
   - This ensures the latest requirements.txt is used
   - Then run: `docker-compose --env-file ../.env -f docker-compose.dev.yml up`

3. **SQL generation fails**
   - Verify COMPLETION_ENDPOINT and COMPLETION_KEY in `../.env`
   - Check QDECOMP_examples.json exists in backend directory
   - Review container logs: `docker-compose logs backend`

4. **Metabase cards not created**
   - Verify METABASE_KEY has sufficient permissions
   - Check collection_id exists in Metabase
   - Ensure MB_EMBED_SECRET is correct in `../.env`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- Create an issue on GitHub
- Contact the development team
- Check the documentation