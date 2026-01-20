import logging
import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.prompts import PromptTemplate
import faiss

logger = logging.getLogger(__name__)

class AnomalyRAG:
    def __init__(self, persist_directory="./anomaly_index", model_name="llama3"):
        self.persist_directory = persist_directory
        self.model_name = model_name
        self.embeddings = OllamaEmbeddings(model=model_name)
        self.llm = Ollama(model=model_name)
        self.vectorstore = None
        
        # Load existing index if available, else initialize new
        if os.path.exists(self.persist_directory):
            try:
                self.vectorstore = FAISS.load_local(
                    self.persist_directory, 
                    self.embeddings,
                    allow_dangerous_deserialization=True # Trusted local file
                )
                logger.info("Loaded existing FAISS index.")
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
        
        if self.vectorstore is None:
            # Initialize empty FAISS index
            # Requires creating a dummy index first or using from_texts with empty list trick if supported, 
            # but FAISS usually needs data to init dimensions.
            # Using a simple trick: index a dummy doc then remove it, or just handle lazy init.
            # Here we'll lazy init on first add, or index a placeholder.
            pass

    def index_anomaly(self, anomaly_record: dict):
        """
        Adds a historical anomaly to the vector store.
        """
        try:
            text = f"Anomaly in {anomaly_record.get('district', 'Unknown')}, {anomaly_record.get('state', 'Unknown')}: {anomaly_record.get('description', '')}. Severity: {anomaly_record.get('severity', 'Unknown')}"
            metadata = {
                "type": anomaly_record.get('type', 'generic'),
                "severity": str(anomaly_record.get('severity', 0)),
                "date": anomaly_record.get('date', '')
            }
            
            if self.vectorstore is None:
                # Create new index with this first text
                self.vectorstore = FAISS.from_texts(
                    texts=[text], 
                    embedding=self.embeddings, 
                    metadatas=[metadata]
                )
            else:
                self.vectorstore.add_texts(texts=[text], metadatas=[metadata])
            
            # Save to disk
            self.vectorstore.save_local(self.persist_directory)
            logger.info(f"Indexed anomaly: {metadata}")
            
        except Exception as e:
            logger.error(f"Error indexing anomaly: {e}")

    def explain_anomaly(self, new_anomaly: dict):
        """
        Retrieves similar anomalies and generates an explanation.
        """
        try:
            if self.vectorstore is None:
                return {
                    "explanation": "No knowledge base available yet. Please index historical anomalies.",
                    "similar_cases": []
                }

            query = f"Anomaly: {new_anomaly.get('anomaly_type', 'Unknown')} in {new_anomaly.get('district', 'Unknown')} with value {new_anomaly.get('anomaly_value', '')}."
            
            # Retrieve similar cases
            similar_docs = self.vectorstore.similarity_search(query, k=3)
            context = "\n".join([f"- {doc.page_content}" for doc in similar_docs])
            
            # Prompt Engineering
            template = """
            You are an expert analyst. Explain the following new anomaly based on similar past cases.
            
            SIMILAR PAST CASES:
            {context}
            
            NEW ANOMALY:
            {query}
            
            TASK:
            1. Suggest likely root causes.
            2. Recommend resolution steps based on past patterns.
            
            Provide a concise explanation.
            """
            
            prompt = PromptTemplate.from_template(template)
            chain = prompt | self.llm
            
            explanation = chain.invoke({"context": context, "query": query})
            
            return {
                "explanation": explanation,
                "similar_cases": [doc.page_content for doc in similar_docs]
            }
            
        except Exception as e:
            logger.error(f"Error explaining anomaly: {e}")
            return {
                "explanation": "Could not generate explanation due to system error.",
                "similar_cases": [],
                "error": str(e)
            }

# Singleton instance
rag_system = AnomalyRAG()
