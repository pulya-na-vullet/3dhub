"""Kafka side-effect checks for SigningDocs on ump.process.from.system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.qa.clients.kafka_probe import (
    InMemoryKafkaProbe,
    assert_signing_docs_message,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestKafkaSigningDocsFromAkhqScreenshot:
    """Replays the AKHQ dump attached to the task as the source of truth."""

    @pytest.fixture
    def akhq_dump(self) -> dict:
        path = FIXTURES / "akhq_ump_process_from_system.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_topic_name(self, akhq_dump: dict, kafka_topic: str) -> None:
        assert akhq_dump["topic"] == kafka_topic
        assert akhq_dump["topic"] == "ump.process.from.system"

    def test_signing_docs_message_present_and_valid(
        self,
        akhq_dump: dict,
        document_uuid: str,
        kafka_schema: dict,
        expected_kafka_message: dict,
    ) -> None:
        probe = InMemoryKafkaProbe(akhq_dump["records"])
        message = probe.find_signing_docs(document_id=document_uuid)
        assert message is not None, "SigningDocs message not found in topic dump"
        assert_signing_docs_message(message, document_id=document_uuid)
        Draft202012Validator(kafka_schema).validate(message)
        assert message == expected_kafka_message

    def test_message_key_matches_document_uuid(
        self,
        akhq_dump: dict,
        document_uuid: str,
    ) -> None:
        matching = [
            r
            for r in akhq_dump["records"]
            if r.get("key") == document_uuid
            and (r.get("value") or {}).get("messageName") == "SigningDocs"
        ]
        assert matching, "Kafka key must equal document UUID for SigningDocs"
        value = matching[0]["value"]
        assert value["applicationId"] == document_uuid
        assert value["variables"]["agreementLink"] == document_uuid
        assert value["correlationKey"].endswith(".NON_CREDIT_INSURANCE")

    def test_unrelated_clm_messages_are_ignored(
        self,
        akhq_dump: dict,
        document_uuid: str,
    ) -> None:
        probe = InMemoryKafkaProbe(akhq_dump["records"])
        message = probe.find_signing_docs(document_id=document_uuid)
        assert message is not None
        assert message["messageName"] == "SigningDocs"
        assert message["messageName"] != "CLM_UPDATE_STATUS"

    def test_missing_document_yields_none(self, akhq_dump: dict) -> None:
        probe = InMemoryKafkaProbe(akhq_dump["records"])
        assert probe.find_signing_docs(document_id="00000000-0000-0000-0000-000000000000") is None
