# OCI Deployment Preparation

This repository can run locally with Ollama or call OCI Generative AI for chat
and embeddings. Keep the first cloud deployment as a private demo/staging system;
do not upload real confidential company documents to a public portfolio instance.

## Current Project Boundaries

- `streamlit_app/utils/api_client.py` has two modes. `API_MODE=mock` preserves the
  standalone demo, while `API_MODE=http` calls the FastAPI service.
- OCI chat and embedding providers are selected independently with
  `LLM_PROVIDER=oci` and `EMBEDDING_PROVIDER=oci`.
- Chroma and uploaded files use local persistent directories. The supplied
  Compose file persists them in Docker volumes for a single-host demo; this is
  not a horizontally scalable storage design.
- The API currently processes document ingestion as an in-process background
  task. Keep one API worker for this deployment; multiple replicas need a
  separate durable job queue and shared vector storage first.
- Production seeding does not create the demo accounts. It requires a bootstrap
  admin supplied through environment secrets and does not automatically ingest
  the sample document.

## 1. Prepare OCI Access

Create an OCI compartment and select a region that offers the chat and embedding
models you want. Use `OCI_COMPARTMENT_ID`, `OCI_REGION`, and optionally
`OCI_SERVICE_ENDPOINT` in the runtime environment. Model availability changes;
verify model IDs in OCI's model discovery page before setting `OCI_CHAT_MODEL`
and `OCI_EMBEDDING_MODEL`.

For a local integration test, configure OCI API-key authentication outside Git.
For a Compute-hosted service, prefer an instance principal with a narrowly scoped
dynamic group policy that grants only the required Generative AI chat and, if
selected, embedding permissions. The official `langchain-oci` package supports
both OCI chat and embedding components.

## 2. Choose Model Providers

To use OCI for both generation and embeddings:

```dotenv
LLM_PROVIDER=oci
EMBEDDING_PROVIDER=oci
OCI_REGION=us-chicago-1
OCI_COMPARTMENT_ID=<your-compartment-ocid>
OCI_AUTH_TYPE=INSTANCE_PRINCIPAL
OCI_CHAT_MODEL=<model-available-in-your-region>
OCI_EMBEDDING_MODEL=<embedding-model-available-in-your-region>
```

You can instead keep `EMBEDDING_PROVIDER=ollama`, but then an Ollama service and
the configured embedding model must remain available to the API. If you change
the embedding provider/model, rebuild the Chroma index by re-ingesting every
document; do not query old vectors using a different embedding model.

## 3. Configure Production Secrets

Set these values using OCI Vault or the deployment platform's secret facility;
do not commit `.env`:

- `ENV=production`
- `JWT_SECRET_KEY` as a unique random secret of at least 32 characters
- `DATABASE_URL` for a private PostgreSQL database using TLS where available
- `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, and a unique
  `BOOTSTRAP_ADMIN_PASSWORD` of at least 16 characters for the first database
  initialization
- `CORS_ALLOWED_ORIGINS` containing only the real UI origin
- Provider, model, compartment, and region settings from the prior section

Never expose the database port, Chroma files, or Ollama's port to the public
internet. The API CORS allow-list is explicit and credentialed CORS is disabled.
After the first admin has been created, remove the bootstrap password from the
runtime secret configuration.

## 4. Test the Containers Locally

Copy `.env.example` to `.env`, replace the database password in both
`POSTGRES_PASSWORD` and `DATABASE_URL`, and leave `ENV=development` for the local
demo stack. Start the local database and Ollama profiles, then download the
configured local models before starting the app:

```bash
docker compose --profile local-db --profile local-ollama up -d postgres ollama
docker compose exec ollama ollama pull phi3:mini
docker compose exec ollama ollama pull nomic-embed-text
docker compose up --build -d api streamlit
```

Open `http://localhost:8501`. The UI uses the actual API in this stack; the
development-only demo accounts are created by the local seed routine. Verify
`http://localhost:8000/health`, login, role separation, document upload, query
sources, and the missing-context fallback.

## 5. Deploy on OCI

For a first single-host demo, create a Linux Compute VM in a VCN. OCI's instance
workflow supports SSH-key access and private/public subnet choices. Restrict SSH
to your own address, and expose only HTTPS through a load balancer or reverse
proxy. Use private networking for the database. Attach durable storage for the
Chroma and uploads volumes if you retain the local file-backed stores.

Set `DATABASE_URL` to the private managed PostgreSQL endpoint. Leave the local
PostgreSQL and Ollama profiles disabled when using managed database/model
services. Build and run the API/UI containers on the VM. Set `API_MODE=http` and
`API_BASE_URL` to the private API service address for Streamlit. Configure
`CORS_ALLOWED_ORIGINS` to the public UI origin, and test OCI authentication from
inside the container before relying on instance-principal access. Do not publish
the OCI API-key file or private key in the image.

Before calling this production-ready, add a durable ingestion queue, backups,
monitoring, rate limiting, secure account provisioning, and a shared vector
store if you need multiple API replicas.
