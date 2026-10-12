"""Simple Streamlit demonstration UI for the local document assistant."""

from dataclasses import replace
from pathlib import Path

from .config import HackathonConfig
from .pipeline import HackathonRAG


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError("Install streamlit from hackathon_requirements.txt") from exc

    st.set_page_config(page_title="Local Document Assistant", page_icon="📚", layout="wide")
    st.title("📚 Local Document Assistant")
    st.caption("Grounded answers from local documents through Ollama")

    defaults = HackathonConfig()
    with st.sidebar:
        st.header("Configuration")
        documents = Path(st.text_input("Documents directory", str(defaults.documents_dir)))
        index = Path(st.text_input("Index directory", str(defaults.index_dir)))
        chat_model = st.text_input("Chat model", defaults.chat_model)
        embedding_model = st.text_input("Embedding model", defaults.embedding_model)
        config = replace(
            defaults,
            documents_dir=documents,
            index_dir=index,
            chat_model=chat_model,
            embedding_model=embedding_model,
        )
        rag = HackathonRAG(config)

        if st.button("Check environment", use_container_width=True):
            st.json(rag.doctor())
        if st.button("Preview chunks", use_container_width=True):
            with st.spinner("Extracting and checking chunks..."):
                try:
                    report = rag.preview(index.parent / "chunk_preview.json", 20)
                    st.success(f"{report['chunks']} chunks from {report['inventory']['supported_files']} files")
                    st.json(report["chunk_lengths"])
                except Exception as exc:
                    st.error(str(exc))
        if st.button("Build index", type="primary", use_container_width=True):
            with st.spinner("Embedding documents and building the index..."):
                try:
                    st.json(rag.ingest(reset=True))
                    st.success("Index is ready")
                except Exception as exc:
                    st.error(str(exc))

    question = st.chat_input("Ask a question about the documents")
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching the documents..."):
                try:
                    result = rag.ask(question)
                    st.write(result.answer)
                    if result.supported:
                        st.success("Supported by the provided documents")
                    else:
                        st.warning("The documents did not provide enough support")
                    if result.citations:
                        st.subheader("Sources")
                        for citation in result.citations:
                            location = citation["source"]
                            if citation.get("page") is not None:
                                location += f" — page {citation['page']}"
                            if citation.get("section"):
                                location += f" — {citation['section']}"
                            st.markdown(f"- **{location}**")
                    with st.expander("Retrieval details"):
                        st.json(result.retrieved)
                    st.caption(f"Answer latency: {result.latency_ms} ms")
                except Exception as exc:
                    st.error(str(exc))
