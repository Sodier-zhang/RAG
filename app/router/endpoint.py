from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.service.service import BailianKnowledgeBaseService, BailianServiceError

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
_service: BailianKnowledgeBaseService | None = None


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, description="Knowledge base name.")
    description: str | None = Field(default=None, description="Knowledge base description.")
    category_id: str | None = Field(default=None, description="Optional existing category ID. Leave empty to auto-create a category.")
    chunk_size: int | None = Field(default=1500, ge=1, le=6000, description="Default chunk size. 1500 is recommended for your current workflow.")
    overlap_size: int | None = Field(default=200, ge=0, le=1024, description="Default overlap size between adjacent chunks.")
    chunk_mode: str | None = Field(default=None, description="Leave empty to use smart chunking.")
    separator: str | None = Field(default=None, description="Only used when chunk_mode is regex.")
    enable_headers: bool | None = Field(default=False, description="Enable only for Excel files with header rows.")
    embedding_model_name: str | None = Field(default="text-embedding-v4", description="Embedding model used by the knowledge base.")
    rerank_model_name: str | None = Field(default="qwen3-rerank", description="Rerank model used during retrieval.")


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
    description="Create a Bailian document retrieval knowledge base. By default it uses smart chunking with chunk_size=1500 and overlap_size=200. If category_id is omitted, the service creates an empty category first and then creates the knowledge base.",
)
async def create_knowledge_base(payload: CreateKnowledgeBaseRequest):
    try:
        return await get_service().create_knowledge_base(**payload.model_dump())
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
)
async def list_default_index_documents():
    try:
        return await get_service().list_index_documents(index_id=None)
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/retrieve",
    summary="Retrieve using default index",
)
async def retrieve_with_default_index(payload: RetrieveRequest):
    try:
        return await get_service().retrieve(index_id=None, **payload.model_dump())
    except BailianServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
