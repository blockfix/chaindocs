# main.py
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from langchain.llms.fake import FakeListLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


# Set up embedding model and in-memory vector store
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
qdrant = QdrantClient(":memory:")
qdrant.recreate_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# Example documents for retrieval
documents = [
    "ChainDocs helps organize your documentation with retrieval augmented generation.",
    "RAG combines search and large language models to answer questions from context.",
]

points = [
    PointStruct(
        id=idx,
        vector=embedding_model.encode(text).tolist(),
        payload={"text": text},
    )
    for idx, text in enumerate(documents)
]
qdrant.upsert(collection_name="docs", points=points)

prompt = PromptTemplate(
    template=(
        "Use the context to answer the question.\n"
        "Context: {context}\n"
        "Question: {question}\n"
        "Answer:"
    ),
    input_variables=["context", "question"],
)

llm = FakeListLLM(responses=["I'm a mock model."])
chain = LLMChain(prompt=prompt, llm=llm)


@app.get("/")
async def spa():
    return FileResponse("index.html")


@app.get("/ask")
def ask(question: str = Query(..., description="Question to ask the knowledge base")):
    query_vector = embedding_model.encode(question).tolist()
    result = qdrant.search(
        collection_name="docs", query_vector=query_vector, limit=1
    )
    context = result[0].payload["text"] if result else ""
    answer = chain.invoke({"context": context, "question": question})["text"]
    return {"answer": answer, "context": context}


@app.get("/health")
def health():
    return {"status": "ChainDocs API is alive!"}

