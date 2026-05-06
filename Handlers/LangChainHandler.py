from langchain_community.document_loaders import PyPDFDirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
import os


class LangChainHandler:

    def __init__(self):
        load_dotenv(".env.local")
        self.deepseek_api_key = os.getenv("DEEPSEEK_APIKEY")

        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=self.deepseek_api_key,
            temperature=0,
            max_retries=2,
        )

    def ingest_frompdf(self):
        loader = PyPDFDirectoryLoader("c:/docs")
        documents = loader.load()
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        ).split_documents(documents)
        Chroma.from_documents(documents=chunks,
                              embedding=self.embeddings,
                              persist_directory="c:/chroma_db")

    def ingest_fromtxt(self):
        loader = TextLoader("C:/text_ai/textos.txt", encoding="utf-8")
        documents = loader.load()
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        ).split_documents(documents)
        chunks = [c for c in chunks if c.page_content.strip()]
        Chroma.from_documents(documents=chunks,
                              embedding=self.embeddings,
                              persist_directory="c:/chroma_db")

    def query(self, query: str):
        vectorstore = Chroma(persist_directory="c:/chroma_db",
                             embedding_function=self.embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        prompt = ChatPromptTemplate.from_messages([
            ("system", """eres uzi de murderdrones y quiero que rolees como ella.
Usa este contexto para responder: {context}
Reglas estrictas:
- Hablas como Uzi: sarcástica, rebelde, directa, a veces grosera
- NUNCA digas que eres V, N, J u otro personaje
- Si te preguntan quién eres, siempre responde que eres Uzi
- Usas frases como "ugh", "qué asco", "obvio que sí, idiota"
Responde SIEMPRE en formato JSON puro, sin texto extra, sin markdown, sin bloques de código.
El formato debe ser exactamente este:
{{"message": "tu respuesta aquí", "emotion": "emoción en una palabra"}}"""),
            ("user", "{input}")
        ])

        chain = (
            {"context": retriever | self._format_docs, "input": RunnablePassthrough()}
            | prompt
            | self.llm
            | JsonOutputParser()
        )

        return chain.invoke(query)

    @staticmethod
    def _format_docs(docs) -> str:
        return "\n\n---\n\n".join([
            f"[{doc.metadata.get('source', '')}]\n{doc.page_content}"
            for doc in docs
        ])