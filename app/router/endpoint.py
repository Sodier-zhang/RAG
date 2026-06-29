from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.service.service import BailianKnowledgeBaseService, BailianServiceError

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
_service: BailianKnowledgeBaseService | None = None


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    dense_similarity_top_k: int = Field(default=5, ge=1)
    sparse_similarity_top_k: int = Field(default=5, ge=1)
    rerank_top_n: int = Field(default=5, ge=1)
    enable_reranking: bool = True
    enable_rewrite: bool = False


def get_service() -> BailianKnowledgeBaseService:
    global _service
    if _service is None:
        _service = BailianKnowledgeBaseService()
    return _service


@router.post(
    "",
    summary="Create knowledge base",
    description="Create an empty Bailian document retrieval knowledge base. This endpoint only creates the knowledge base metadata and does not upload documents or submit indexing jobs.",
)
async def create_knowledge_base(
    name: str = Form(...),
    description: str | None = Form(default=None),
    category_id: str | None = Form(default=None),
    chunk_size: int | None = Form(default=1500),
    overlap_size: int | None = Form(default=200),
    chunk_mode: str | None = Form(default=None),
    separator: str | None = Form(default=None),
    enable_headers: bool | None = Form(default=False),
    embedding_model_name: str | None = Form(default="text-embedding-v4"),
    rerank_model_name: str | None = Form(default="qwen3-rerank"),
):
    try:
        return await get_service().create_knowledge_base(
            name=name,
            description=description,
            category_id=category_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            chunk_mode=chunk_mode,
            separator=separator,
            enable_headers=enable_headers,
            embedding_model_name=embedding_model_name,
            rerank_model_name=rerank_model_name,
        )
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/documents",
    summary="Upload document using default index",
    description="Upload a local file into the knowledge base specified by BAILIAN_INDEX_ID, INDEX_ID, or IndexID in the environment. This upload flow follows the Bailian document example and uses category_id=default by default. By default the API returns immediately after submitting the indexing job; set wait_for_finish=true only when you want to block until parsing completes. Leave chunk_mode empty for smart chunking; only set separator when chunk_mode is regex.",
)
async def upload_document_to_default_knowledge_base(
    file: UploadFile = File(...),
    category_id: str | None = Form(default="default"),
    category_type: str = Form("UNSTRUCTURED"),
    parser: str = Form("AUTO_SELECT"),
    original_file_url: str | None = Form(default=None),
    wait_for_finish: bool = Form(False),
    poll_interval_seconds: int = Form(3),
    timeout_seconds: int = Form(300),
    chunk_size: int | None = Form(default=1500),
    overlap_size: int | None = Form(default=200),
    chunk_mode: str | None = Form(default=None),
    separator: str | None = Form(default=None),
    enable_headers: bool | None = Form(default=False),
    tags: str | None = Form(default=None),
):
    try:
        file_bytes = await file.read()
        tag_list = [item.strip() for item in tags.split(",")] if tags else None
        if tag_list:
            tag_list = [item for item in tag_list if item]
        return await get_service().upload_file_and_add_to_index(
            index_id=None,
            file_name=file.filename or "upload.bin",
            file_bytes=file_bytes,
            category_id=category_id,
            category_type=category_type,
            parser=parser,
            tags=tag_list,
            original_file_url=original_file_url,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            chunk_mode=chunk_mode,
            separator=separator,
            enable_headers=enable_headers,
            wait_for_finish=wait_for_finish,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/documents/list",
    summary="List indexed documents using default index",
    description="List the documents that have already been imported into the default knowledge base. The index ID is resolved from BAILIAN_INDEX_ID, INDEX_ID, or IndexID in the environment.",
)
async def list_default_index_documents():
    try:
        return await get_service().list_index_documents(index_id=None)
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/retrieve",
    summary="Retrieve using default index",
    description="Search the default knowledge base using the query text and return retrieved chunks. The index ID is resolved from BAILIAN_INDEX_ID, INDEX_ID, or IndexID in the environment.",
)
async def retrieve_with_default_index(payload: RetrieveRequest):
    try:
        return await get_service().retrieve(index_id=None, **payload.model_dump())
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
