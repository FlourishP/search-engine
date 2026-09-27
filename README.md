# Search Engine

Full-text search engine with fuzzy matching, autocomplete, and relevance scoring.

## Features
- **Full-Text Search**: Elasticsearch-powered search with fuzzy matching
- **Autocomplete**: Type-ahead suggestions with ranking
- **Relevance Scoring**: BM25 + custom boost factors
- **Faceted Search**: Filter by categories, date ranges, tags
- **Analytics**: Search query analytics and performance metrics

## Tech Stack
- **Search**: Elasticsearch
- **Backend**: Python, FastAPI
- **Frontend**: React, TypeScript
- **Database**: PostgreSQL (metadata)
- **Cache**: Redis

## Quick Start
```bash
git clone https://github.com/FlourishP/search-engine
cd search-engine
docker-compose up -d
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

## License
MIT — see [LICENSE](LICENSE)
