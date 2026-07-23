"""End-to-end happy path for AlfaCapture2 cms-links (API + Kafka).

By default runs against mocks (offline CI).
Set QA_LIVE_API=1 (+ QA_BEARER_TOKEN) to hit corp-gateway-test.
Set QA_LIVE_KAFKA=1 (+ QA_KAFKA_BOOTSTRAP) to poll real topic.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from tests.qa.clients.cms_links_client import CmsLinksClient
from tests.qa.clients.contract_checks import (
    assert_alfacapture_request,
    assert_success_response,
)
from tests.qa.clients.kafka_probe import (
    InMemoryKafkaProbe,
    LiveKafkaProbe,
    assert_signing_docs_message,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _mock_success_response(document_uuid: str) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = [
        {
            "documentType": "agreement",
            "documentId": document_uuid,
            "resultCode": 0,
        }
    ]
    return response


class TestCmsLinksAlfaCaptureHappyPathOffline:
    def test_api_success_and_kafka_signing_docs(
        self,
        alfacapture_cms_links_payload: dict,
        document_uuid: str,
        api_base_url: str,
        api_headers: dict,
        kafka_schema: dict,
        response_schema: dict,
    ) -> None:
        from jsonschema import Draft202012Validator

        assert_alfacapture_request(alfacapture_cms_links_payload)

        session = MagicMock()
        session.post.return_value = _mock_success_response(document_uuid)
        client = CmsLinksClient(api_base_url, api_headers, session=session)

        http_response = client.post_cms_links(alfacapture_cms_links_payload)
        assert http_response.status_code == 200
        body = http_response.json()
        Draft202012Validator(response_schema).validate(body)
        assert_success_response(body, document_id=document_uuid)

        session.post.assert_called_once()
        call_kwargs = session.post.call_args
        assert call_kwargs.kwargs["json"]["documents"][0]["documentType"] == "agreement"
        assert call_kwargs.kwargs["json"]["documents"][0]["alfaCaptureDocId"] == document_uuid

        dump = json.loads(
            (FIXTURES / "akhq_ump_process_from_system.json").read_text(encoding="utf-8")
        )
        probe = InMemoryKafkaProbe(dump["records"])
        kafka_msg = probe.find_signing_docs(document_id=document_uuid)
        assert kafka_msg is not None
        assert_signing_docs_message(kafka_msg, document_id=document_uuid)
        Draft202012Validator(kafka_schema).validate(kafka_msg)


@pytest.mark.live
class TestCmsLinksAlfaCaptureLive:
    def test_live_api_returns_result_code_zero(
        self,
        live_api_enabled: bool,
        alfacapture_cms_links_payload: dict,
        document_uuid: str,
        api_base_url: str,
        api_headers: dict,
        response_schema: dict,
    ) -> None:
        if not live_api_enabled:
            pytest.skip("Set QA_LIVE_API=1 to run against corp-gateway-test")
        if not api_headers.get("authorization"):
            pytest.skip("QA_BEARER_TOKEN is required for live API")

        from jsonschema import Draft202012Validator

        assert_alfacapture_request(alfacapture_cms_links_payload)
        client = CmsLinksClient(api_base_url, api_headers)
        response = client.post_cms_links(alfacapture_cms_links_payload)
        assert response.status_code == 200, response.text
        body = response.json()
        Draft202012Validator(response_schema).validate(body)
        assert_success_response(body, document_id=document_uuid)

    def test_live_kafka_contains_signing_docs(
        self,
        live_kafka_enabled: bool,
        kafka_bootstrap: str | None,
        kafka_topic: str,
        document_uuid: str,
        kafka_schema: dict,
    ) -> None:
        if not live_kafka_enabled:
            pytest.skip("Set QA_LIVE_KAFKA=1 to poll ump.process.from.system")
        if not kafka_bootstrap:
            pytest.skip("QA_KAFKA_BOOTSTRAP is required for live Kafka")

        from jsonschema import Draft202012Validator

        probe = LiveKafkaProbe(kafka_bootstrap, kafka_topic)
        try:
            message = probe.find_signing_docs(document_id=document_uuid, timeout_sec=60)
        finally:
            probe.close()

        assert message is not None, (
            f"SigningDocs for {document_uuid} not found in {kafka_topic}"
        )
        assert_signing_docs_message(message, document_id=document_uuid)
        Draft202012Validator(kafka_schema).validate(message)
