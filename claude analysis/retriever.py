import os

from src.vectorstores.unified_store_adapter import UnifiedStoreAdapter
from src.utils.embedding_utils import get_embedding_model

from src.core.config import load_config

# Load configuration file
config = load_config()
re_process_data = config["re_process_data"]
provider = config["vectorstore"]["provider"].lower()
index_name = config["vectorstore"]["index_name"]

# Build the full path: vector_store/{index_name}
# Path building
base_dir = "vector_store" 
FAISS_STORE_PATH = os.path.join(base_dir, index_name)

# ------------------ Build or load vector store ------------------
def setup_retriever():
    # Optional: Only print debug in development
    # print(f"🔍 Current working directory: {os.getcwd()}")
    # print(f"🔍 FAISS_STORE_PATH: {FAISS_STORE_PATH}")
    # print(f"🔍 Path exists: {os.path.exists(FAISS_STORE_PATH)}")
    
    embedding_model = get_embedding_model()  

    store = UnifiedStoreAdapter(
        provider,
        index_name,
        cfg=config,
        embeddings=embedding_model,
    )

    vector_store = None
    
    # For FAISS: Chevck local file system
    if provider == "faiss":
        print(f"✅  value  FAISS vect: {FAISS_STORE_PATH}")
        print(f"✅ re_process_data: {re_process_data}")

        if os.path.exists(FAISS_STORE_PATH) and not re_process_data:
            print(f"✅ Loading existing FAISS vector store from: {FAISS_STORE_PATH}")
            try:
                vector_store = store.from_existing_index(index_name, embedding_model)
                print("✅ Successfully loaded FAISS index")
            except Exception as e:
                print(f"⚠️ Failed to load from disk: {e}. Will recreate...")
                vector_store = None
        
        # If load failed or doesn't exist, create new
        if vector_store is None:
            raise FileNotFoundError(f"❌ Critical Error: FAISS index not found at {FAISS_STORE_PATH}. Please build it locally using train_local.py and mount it.")
    
    # For cloud providers (Pinecone, Chroma, etc.)
    else:
        if store.list_indexes().names() and not re_process_data:
            print("✅ Cloud index exists. Connecting...")
            vector_store = store.from_existing_index(index_name, embedding_model)
        else:
            raise Exception(f"❌ Critical Error: Cloud index '{index_name}' does not exist. Please build it locally first.")
    
    # ------------------ Retriever setup (COMMON for both) ------------------
    
    # ✅ Normal vector similarity retriever
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 10})
    
    # ------------------ Hybrid retriever ------------------
    # if use_keyword_in_meta_data:
    # print("🔍 Setting up hybrid retriever with BM25...")
        
    #     # ✅ FIX: Get documents whether creating new or loading existing
    # if docs_chunked is not None:
    #         # Creating new index - use the chunks we just created
    #         documents = [
    #             Document(page_content=chunk["text"], metadata=chunk["metadata"])
    #             for chunk in docs_chunked
    #         ]
    # else:
    #         # Loading existing index - reconstruct documents from vector store
    #         print("📝 Reconstructing documents for BM25 from vector store...")
    #         documents = []
    #         try:
    #             # Get all documents from FAISS docstore
    #             for doc_id in vector_store.index_to_docstore_id.values():
    #                 doc = vector_store.docstore.search(doc_id)
    #                 if doc:
    #                     documents.append(doc)
    #         except Exception as e:
    #             print(f"⚠️ Could not reconstruct documents for BM25: {e}")
    #             print("⚠️ Hybrid retriever disabled, using vector search only")
    #             return retriever
        
    # if documents:
    #         keyword_retriever = BM25Retriever.from_documents(documents)
    #         keyword_retriever.k = 10
            
    #         retriever = EnsembleRetriever(
    #             retrievers=[retriever, keyword_retriever],
    #             weights=[0.6, 0.4],
    #         )
    #         print("✅ Hybrid retriever enabled!")
    # else:
    #         print("⚠️ No documents found for BM25, using vector search only")
    
    return retriever