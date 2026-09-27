"""Search Engine — Full-text search with fuzzy matching and autocomplete.

Python, Elasticsearch, FastAPI, React.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from elasticsearch import Elasticsearch
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Search Engine", version="1.0.0")

es = Elasticsearch(
    [os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")],
    basic_auth=(os.getenv("ES_USER", "elastic"), os.getenv("ES_PASSWORD", "changeme")),
)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
)

INDEX_NAME = "search_index"


class Document(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str] = []
    metadata: Optional[dict] = None


class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    score: float
    tags: List[str]


@app.get("/health")
def health():
    es_ok = False
    try:
        es_ok = es.ping()
    except Exception:
        pass
    return {"status": "ok", "elasticsearch": es_ok, "timestamp": datetime.utcnow().isoformat()}


@app.post("/index")
def index_document(doc: Document):
    """Index a document for search."""
    try:
        es.index(index=INDEX_NAME, id=doc.id, document=doc.dict())
        redis_client.setex(f"doc:{doc.id}", 3600, "1")
        return {"status": "indexed", "id": doc.id}
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/bulk")
def bulk_index(documents: List[Document]):
    """Index multiple documents."""
    from elasticsearch.helpers import bulk

    actions = [
        {
            "_index": INDEX_NAME,
            "_id": doc.id,
            "_source": doc.dict(),
        }
        for doc in documents
    ]
    try:
        success, failed = bulk(es, actions, raise_on_error=False)
        return {"indexed": success, "failed": len(failed)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    size: int = Query(10, ge=1, le=100),
    fuzzy: bool = Query(True, description="Enable fuzzy matching"),
):
    """Search indexed documents with fuzzy matching and autocomplete."""
    fuzzy_param = "AUTO" if fuzzy else None

    query = {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": q,
                        "fields": ["title^3", "content", "tags^2"],
                        "fuzziness": fuzzy_param,
                        "prefix_length": 2,
                    }
                },
                {"match_phrase": {"content": q}},
            ],
            "minimum_should_match": 1,
        }
    }

    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query["bool"]["filter"] = [{"terms": {"tags": tag_list}}]

    try:
        response = es.search(index=INDEX_NAME, query=query, size=size)
        results = [
            SearchResult(
                id=hit["_id"],
                title=hit["_source"]["title"],
                content=hit["_source"]["content"][:200],
                score=hit["_score"],
                tags=hit["_source"].get("tags", []),
            )
            for hit in response["hits"]["hits"]
        ]
        return {"query": q, "results": results, "total": response["hits"]["total"]["value"]}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/autocomplete")
def autocomplete(q: str = Query(..., min_length=1)):
    """Get autocomplete suggestions."""
    cache_key = f"ac:{q}"
    cached = redis_client.get(cache_key)
    if cached:
        return {"query": q, "suggestions": eval(cached), "cached": True}

    query = {
        "suggest": {
            "text": q,
            "simple_phrase": {
                "phrase": {
                    "field": "title",
                    "size": 5,
                    "direct_generator": [{"field": "title", "suggest_mode": "always"}],
                }
            },
        }
    }

    try:
        response = es.search(index=INDEX_NAME, body=query)
        suggestions = []
        for opt in response["suggest"]["simple_phrase"][0]["options"]:
            suggestions.append(opt["text"])
        redis_client.setex(cache_key, 300, str(suggestions))
        return {"query": q, "suggestions": suggestions, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/index/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document from the index."""
    try:
        es.delete(index=INDEX_NAME, id=doc_id, ignore=[404])
        return {"status": "deleted", "id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)