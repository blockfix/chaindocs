# Chaindocs

## Deployment

Deploying to [Render](https://render.com/):

- **Root Directory**: `chaindocs`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Environment Variables

The API expects a Qdrant vector database for retrieval. Configure it with:

- `QDRANT_URL` – URL of your Qdrant service.
- `QDRANT_API_KEY` – API key for that service.
- `QDRANT_COLLECTION` – collection name (defaults to `chaindocs`).

Leaving `QDRANT_URL` or `QDRANT_API_KEY` unset will disable Qdrant integration; in
that case the `/ask` endpoint responds with an error indicating the missing
configuration. This can be useful for local development.

