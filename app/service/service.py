from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import requests
from alibabacloud_bailian20231229 import models
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_tea_openapi import models as open_api_models

from app.config import AppConfig, get_config


class BailianServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BailianKnowledgeBaseService:
    def __init__(self, settings: AppConfig | None = None):
        try:
            self.settings = settings or get_config()
        except ValueError as exc:
            raise BailianServiceError(str(exc), status_code=500) from exc
        self.client = BailianClient(
            open_api_models.Config(
                access_key_id=self.settings.access_key_id,
                access_key_secret=self.settings.access_key_secret,
                region_id=self.settings.region_id,
            )
        )

    def resolve_index_id(self, index_id: str | None = None) -> str:
        resolved_index_id = index_id or self.settings.default_index_id
        if not resolved_index_id:
            raise BailianServiceError(
                "Missing index_id. Provide it in the request or set BAILIAN_INDEX_ID/INDEX_ID/IndexID in the environment.",
                status_code=400,
            )
        return resolved_index_id

    @staticmethod
    def normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "string":
            return None
        return cleaned

    def normalize_chunk_mode(self, chunk_mode: str | None) -> str | None:
        normalized = self.normalize_optional_text(chunk_mode)
        if normalized is None:
            return None

        allowed_modes = {"length", "page", "h1", "h2", "regex"}
        if normalized not in allowed_modes:
            raise BailianServiceError(
                f"Invalid chunk_mode: {normalized}. Allowed values are: {', '.join(sorted(allowed_modes))}.",
                status_code=400,
            )
        return normalized

    async def create_knowledge_base(
        self,
        *,
        name: str,
        description: str | None = None,
        category_id: str | None = None,
        chunk_size: int | None = 1500,
        overlap_size: int | None = 200,
        chunk_mode: str | None = None,
        separator: str | None = None,
        enable_headers: bool | None = None,
        embedding_model_name: str | None = None,
        rerank_model_name: str | None = None,
    ) -> dict[str, Any]:
        target_category_id = category_id or await self.create_empty_category(name)
        request = models.CreateIndexRequest(
            name=name,
            description=description,
            category_ids=[target_category_id],
            source_type="DATA_CENTER_CATEGORY",
            structure_type="unstructured",
            sink_type="BUILT_IN",
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            chunk_mode=chunk_mode,
            separator=separator,
            enable_headers=enable_headers,
            embedding_model_name=embedding_model_name,
            rerank_model_name=rerank_model_name,
        )
        response = await self.client.create_index_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "CreateIndex")
        return {
            "index_id": body.data.id,
            "category_id": target_category_id,
            "request_id": body.request_id,
        }

    def resolve_upload_category_id(self, category_id: str | None = None) -> str:
        if category_id:
            return category_id
        if self.settings.default_category_id:
            return self.settings.default_category_id
        return "default"

    async def create_empty_category(self, base_name: str) -> str:
        category_name = self._build_category_name(base_name)
        request = models.AddCategoryRequest(
            category_name=category_name,
            category_type="UNSTRUCTURED",
        )
        response = await self.client.add_category_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "AddCategory")
        return body.data.category_id

    async def upload_file_and_add_to_index(
        self,
        *,
        index_id: str | None,
        file_name: str,
        file_bytes: bytes,
        category_id: str | None = "default",
        category_type: str = "UNSTRUCTURED",
        parser: str = "AUTO_SELECT",
        tags: list[str] | None = None,
        original_file_url: str | None = None,
        chunk_size: int | None = 1500,
        overlap_size: int | None = 200,
        chunk_mode: str | None = None,
        separator: str | None = None,
        enable_headers: bool | None = None,
        wait_for_finish: bool = False,
        poll_interval_seconds: int = 3,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        resolved_index_id = self.resolve_index_id(index_id)
        upload_category_id = self.resolve_upload_category_id(self.normalize_optional_text(category_id) or "default")
        parser = self.normalize_optional_text(parser) or "AUTO_SELECT"
        original_file_url = self.normalize_optional_text(original_file_url)
        chunk_mode = self.normalize_chunk_mode(chunk_mode)
        separator = self.normalize_optional_text(separator)

        if chunk_mode != "regex":
            separator = None

        lease = await self._apply_file_upload_lease(
            category_id=upload_category_id,
            category_type=category_type,
            file_name=file_name,
            file_bytes=file_bytes,
        )
        await self._upload_file_to_lease(file_bytes=file_bytes, lease=lease)
        file_id = await self._add_file_record(
            category_id=upload_category_id,
            category_type=category_type,
            lease_id=lease.file_upload_lease_id,
            parser=parser,
            tags=tags,
            original_file_url=original_file_url,
        )
        job_id = await self._submit_index_add_documents_job(
            index_id=resolved_index_id,
            document_ids=[file_id],
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            chunk_mode=chunk_mode,
            separator=separator,
            enable_headers=enable_headers,
        )

        result: dict[str, Any] = {
            "file_id": file_id,
            "job_id": job_id,
            "index_id": resolved_index_id,
            "category_id": upload_category_id,
            "status": "RUNNING",
        }
        if wait_for_finish:
            result["job"] = await self.wait_for_index_job(
                index_id=index_id,
                job_id=job_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
            )
            result["documents"] = await self.list_index_documents(index_id=index_id)
            result["status"] = result["job"]["status"]
        return result

    async def get_index_job_status(self, *, index_id: str | None, job_id: str) -> dict[str, Any]:
        resolved_index_id = self.resolve_index_id(index_id)
        request = models.GetIndexJobStatusRequest(index_id=resolved_index_id, job_id=job_id)
        response = await self.client.get_index_job_status_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "GetIndexJobStatus")
        documents = [
            {
                "doc_id": item.doc_id,
                "doc_name": item.doc_name,
                "status": item.status,
                "code": item.code,
                "message": item.message,
                "gmt_modified": item.gmt_modified,
            }
            for item in (body.data.documents or [])
        ]
        return {
            "job_id": body.data.job_id,
            "status": body.data.status,
            "documents": documents,
        }

    async def wait_for_index_job(
        self,
        *,
        index_id: str | None,
        job_id: str,
        poll_interval_seconds: int = 3,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            status = await self.get_index_job_status(index_id=index_id, job_id=job_id)
            if status["status"] == "FINISH":
                return status
            if status["status"] in {"FAIL", "FAILED", "ERROR"}:
                raise BailianServiceError(f"Index job failed: {status}", status_code=502)
            await asyncio.sleep(poll_interval_seconds)
        raise BailianServiceError(
            f"Timed out waiting for index job {job_id} to finish.",
            status_code=504,
        )

    async def list_index_documents(self, *, index_id: str | None) -> list[dict[str, Any]]:
        resolved_index_id = self.resolve_index_id(index_id)
        request = models.ListIndexDocumentsRequest(index_id=resolved_index_id, page_number=1, page_size=100)
        response = await self.client.list_index_documents_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "ListIndexDocuments")
        return [
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "source_id": item.source_id,
                "document_type": item.document_type,
                "size": item.size,
                "code": item.code,
                "message": item.message,
                "gmt_modified": item.gmt_modified,
            }
            for item in (body.data.documents or [])
        ]

    async def retrieve(
        self,
        *,
        index_id: str | None,
        query: str,
        dense_similarity_top_k: int = 5,
        sparse_similarity_top_k: int = 5,
        rerank_top_n: int = 5,
        enable_reranking: bool = True,
        enable_rewrite: bool = False,
    ) -> dict[str, Any]:
        resolved_index_id = self.resolve_index_id(index_id)
        request = models.RetrieveRequest(
            index_id=resolved_index_id,
            query=query,
            dense_similarity_top_k=dense_similarity_top_k,
            sparse_similarity_top_k=sparse_similarity_top_k,
            rerank_top_n=rerank_top_n,
            enable_reranking=enable_reranking,
            enable_rewrite=enable_rewrite,
        )
        response = await self.client.retrieve_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "Retrieve")
        return {
            "nodes": [
                {
                    "text": item.text,
                    "score": item.score,
                    "metadata": item.metadata,
                }
                for item in (body.data.nodes or [])
            ],
            "request_id": body.request_id,
        }

    async def _apply_file_upload_lease(
        self,
        *,
        category_id: str,
        category_type: str,
        file_name: str,
        file_bytes: bytes,
    ):
        request = models.ApplyFileUploadLeaseRequest(
            category_type=category_type,
            file_name=file_name,
            md_5=self._md5_hex(file_bytes),
            size_in_bytes=str(len(file_bytes)),
            use_internal_endpoint=False,
        )
        response = await self.client.apply_file_upload_lease_async(
            category_id,
            self.settings.workspace_id,
            request,
        )
        body = self._ensure_success(response.body, "ApplyFileUploadLease")
        return body.data

    async def _upload_file_to_lease(self, *, file_bytes: bytes, lease: Any) -> None:
        raw_headers = dict(lease.param.headers or {})
        if "X-bailian-extra" in raw_headers or "Content-Type" in raw_headers:
            headers = {
                key: value
                for key, value in {
                    "X-bailian-extra": raw_headers.get("X-bailian-extra"),
                    "Content-Type": raw_headers.get("Content-Type"),
                }.items()
                if value is not None
            }
        else:
            headers = {key: value for key, value in raw_headers.items() if value is not None}

        def _send() -> requests.Response:
            return requests.request(
                method=lease.param.method or "PUT",
                url=lease.param.url,
                headers=headers,
                data=file_bytes,
                timeout=120,
            )

        upload_response = await asyncio.to_thread(_send)
        if upload_response.status_code >= 400:
            raise BailianServiceError(
                f"Upload file to lease failed with status {upload_response.status_code}: {upload_response.text}",
                status_code=502,
            )

    async def _add_file_record(
        self,
        *,
        category_id: str,
        category_type: str,
        lease_id: str,
        parser: str,
        tags: list[str] | None,
        original_file_url: str | None,
    ) -> str:
        request = models.AddFileRequest(
            category_id=category_id,
            category_type=category_type,
            lease_id=lease_id,
            parser=parser,
            tags=tags,
            original_file_url=original_file_url,
        )
        response = await self.client.add_file_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "AddFile")
        return body.data.file_id

    async def _submit_index_add_documents_job(
        self,
        *,
        index_id: str,
        document_ids: list[str],
        chunk_size: int | None,
        overlap_size: int | None,
        chunk_mode: str | None,
        separator: str | None,
        enable_headers: bool | None,
    ) -> str:
        request = models.SubmitIndexAddDocumentsJobRequest(
            index_id=index_id,
            document_ids=document_ids,
            source_type="DATA_CENTER_FILE",
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            chunk_mode=chunk_mode,
            separator=separator,
            enable_headers=enable_headers,
        )
        response = await self.client.submit_index_add_documents_job_async(self.settings.workspace_id, request)
        body = self._ensure_success(response.body, "SubmitIndexAddDocumentsJob")
        return body.data.id

    @staticmethod
    def _ensure_success(body: Any, action: str):
        if getattr(body, "success", False):
            return body
        raise BailianServiceError(
            f"{action} failed: {getattr(body, 'message', 'unknown error')}",
            status_code=502,
        )

    @staticmethod
    def _md5_hex(file_bytes: bytes) -> str:
        return hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()

    @staticmethod
    def _build_category_name(base_name: str) -> str:
        cleaned = "".join(char for char in base_name if char.isalnum() or char in "-_:. ").strip()
        cleaned = cleaned or "kb"
        suffix = str(int(time.time()))[-6:]
        prefix = cleaned[:13].strip() or "kb"
        return f"{prefix}-{suffix}"[:20]


def save_upload_to_temp(file_name: str, file_bytes: bytes) -> Path:
    suffix = Path(file_name).suffix
    fd, raw_path = tempfile.mkstemp(suffix=suffix)
    Path(raw_path).write_bytes(file_bytes)
    return Path(raw_path)
