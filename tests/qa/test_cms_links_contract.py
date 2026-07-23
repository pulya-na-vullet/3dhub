"""Contract tests: request/response schemas + AlfaCapture2 field rules."""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.qa.clients.contract_checks import (
    CmsLinksContractError,
    assert_alfacapture_request,
    assert_success_response,
)


class TestCmsLinksRequestContract:
    def test_example_alfacapture_payload_matches_schema(
        self,
        request_schema: dict,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        Draft202012Validator(request_schema).validate(alfacapture_cms_links_payload)

    def test_requires_alfacapture_doc_id_and_agreement_type(
        self,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        assert_alfacapture_request(alfacapture_cms_links_payload)
        doc = alfacapture_cms_links_payload["documents"][0]
        assert doc["documentType"] == "agreement"
        assert doc["alfaCaptureDocId"]
        assert doc["alfaCaptureDocId"] == doc["documentId"]

    def test_rejects_missing_alfa_capture_doc_id(
        self,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        payload = copy.deepcopy(alfacapture_cms_links_payload)
        del payload["documents"][0]["alfaCaptureDocId"]
        with pytest.raises(CmsLinksContractError, match="alfaCaptureDocId"):
            assert_alfacapture_request(payload)

    def test_rejects_non_agreement_document_type(
        self,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        payload = copy.deepcopy(alfacapture_cms_links_payload)
        payload["documents"][0]["documentType"] = "paymentRub"
        with pytest.raises(CmsLinksContractError, match='documentType="agreement"'):
            assert_alfacapture_request(payload)

    def test_schema_rejects_missing_required_top_level(
        self,
        request_schema: dict,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        payload = copy.deepcopy(alfacapture_cms_links_payload)
        del payload["userId"]
        with pytest.raises(ValidationError):
            Draft202012Validator(request_schema).validate(payload)

    def test_legacy_ea_fields_are_optional_for_alfacapture(
        self,
        request_schema: dict,
        alfacapture_cms_links_payload: dict,
    ) -> None:
        """AlfaCapture2 path: url/itemId must not be required."""
        doc = alfacapture_cms_links_payload["documents"][0]
        assert "url" not in doc
        assert "itemId" not in doc
        Draft202012Validator(request_schema).validate(alfacapture_cms_links_payload)


class TestCmsLinksResponseContract:
    def test_success_response_matches_schema(
        self,
        response_schema: dict,
        expected_success_response: list[dict],
    ) -> None:
        Draft202012Validator(response_schema).validate(expected_success_response)

    def test_success_means_result_code_zero(
        self,
        expected_success_response: list[dict],
        document_uuid: str,
    ) -> None:
        assert_success_response(
            expected_success_response,
            document_id=document_uuid,
            document_type="agreement",
        )

    def test_nonzero_result_code_is_failure(
        self,
        document_uuid: str,
    ) -> None:
        body = [
            {
                "documentType": "agreement",
                "documentId": document_uuid,
                "resultCode": 1,
            }
        ]
        with pytest.raises(CmsLinksContractError, match="resultCode=0"):
            assert_success_response(body, document_id=document_uuid)
