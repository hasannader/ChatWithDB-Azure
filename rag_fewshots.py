import os
import hashlib
from typing import List

from langchain_community.document_loaders import JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings

from openai import AzureOpenAI

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, HnswConfigDiff
from qdrant_client.http.models import PayloadSchemaType


# =========================================================
# Load & Split Documents
# =========================================================
def load_and_split_documents() -> List:
    base_dir_path = os.path.join(os.path.dirname(__file__), "assets")
    json_path = os.path.join(base_dir_path, "fewshots.json")

    loader = JSONLoader(
        file_path=json_path,
        jq_schema=".[]",
        text_content=False,
    )
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )

    return splitter.split_documents(docs)


# =========================================================
# Azure Embedding Wrapper
# =========================================================
class AzureEmbeddingWrapper(Embeddings):
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version="2024-12-01-preview",
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        )
        self.deployment = "text-embedding-3-small"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.deployment,
            input=texts
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.deployment,
            input=text
        )
        return response.data[0].embedding


# =========================================================
# Vector Store Manager (Singleton)
# =========================================================
class VectorStoreManager:
    _instance = None

    def __new__(cls, collection_name="fewshots"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, collection_name="fewshots"):
        if hasattr(self, "initialized"):
            return

        self.collection_name = collection_name

        # Embeddings
        self.embeddings = AzureEmbeddingWrapper()

        # Qdrant client
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )

        # Ensure collection exists
        self._ensure_collection()

        # Vector store
        self.vectorstore = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )

        self.initialized = True

    # -----------------------------------------------------
    def _ensure_collection(self):
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=1536,  # for text-embedding-3-small
                    distance=Distance.COSINE,
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                ),
            )

            # Optional metadata indexes
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="candidate_name",
                field_schema=PayloadSchemaType.KEYWORD,
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="section",
                field_schema=PayloadSchemaType.KEYWORD,
            )

    # -----------------------------------------------------
    def add_documents(self, documents: List):
        # prevent duplicate insertion
        existing_count = self.client.count(self.collection_name).count
        if existing_count > 0:
            return

        ids = []
        for doc in documents:
            unique_string = (
                doc.page_content +
                doc.metadata.get("source", "")
            )
            chunk_id = hashlib.md5(unique_string.encode()).hexdigest()
            ids.append(chunk_id)

        self.vectorstore.add_documents(documents, ids=ids)

    # -----------------------------------------------------
    def get_retriever(self, k=5):
        return self.vectorstore.as_retriever(
            search_type="mmr",  # better than similarity
            search_kwargs={
                "k": k,
                "fetch_k": 20
            }
        )


# =========================================================
# Initialize (run once)
# =========================================================
vector_manager = VectorStoreManager()
chunks = load_and_split_documents()
vector_manager.add_documents(chunks)


# =========================================================
# Query Function
# =========================================================
def query_relevant_chunks(query: str) -> List[str]:
    retriever = vector_manager.get_retriever(k=5)
    docs = retriever.invoke(query)

    return [doc.page_content for doc in docs]