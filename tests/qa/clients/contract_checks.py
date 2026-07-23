"""Validators for AlfaCapture2 cms-links request specifics."""

from __future__ import annotations

from typing import Any


class CmsLinksContractError(AssertionError):
    """Raised when request/response violates QA contract checks."""


def assert_alfacapture_document(document: dict[str, Any]) -> None:
    """
    AlfaCapture2 path must carry:
    - documentType == "agreement"
    - alfaCaptureDocId present and equal to documentId (typical happy path)
    and must NOT rely on legacy url/itemId.
    """
    if "documentType" not in document:
        raise CmsLinksContractError("documents[].documentType is required")
    if document["documentType"] != "agreement":
        raise CmsLinksContractError(
            f'expected documentType="agreement", got {document["documentType"]!r}'
        )
    if not document.get("alfaCaptureDocId"):
        raise CmsLinksContractError(
            "alfaCaptureDocId is required for AlfaCapture2 cms-links flow"
        )
    if "documentId" not in document or not document["documentId"]:
        raise CmsLinksContractError("documents[].documentId is required")


def assert_alfacapture_request(payload: dict[str, Any]) -> None:
    for field in ("userId", "systemName", "documents"):
        if field not in payload:
            raise CmsLinksContractError(f"request.{field} is required")
    if not isinstance(payload["documents"], list) or not payload["documents"]:
        raise CmsLinksContractError("request.documents must be a non-empty array")
    for doc in payload["documents"]:
        assert_alfacapture_document(doc)


def assert_success_response(
    response_body: list[dict[str, Any]],
    *,
    document_id: str,
    document_type: str = "agreement",
) -> None:
    if not isinstance(response_body, list) or not response_body:
        raise CmsLinksContractError("response must be a non-empty array")
    item = response_body[0]
    if item.get("documentType") != document_type:
        raise CmsLinksContractError(
            f'expected response documentType={document_type!r}, got {item.get("documentType")!r}'
        )
    if item.get("documentId") != document_id:
        raise CmsLinksContractError(
            f"expected response documentId={document_id!r}, got {item.get('documentId')!r}"
        )
    if item.get("resultCode") != 0:
        raise CmsLinksContractError(
            f"expected resultCode=0 (success), got {item.get('resultCode')!r}"
        )
