"""Kafka helpers for ump.process.from.system SigningDocs checks."""

from __future__ import annotations

import json
import time
from typing import Any, Callable


class InMemoryKafkaProbe:
    """Test double: search preloaded records the way AKHQ/consumer would."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def find_signing_docs(
        self,
        *,
        document_id: str,
        timeout_sec: float = 0.0,
    ) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout_sec
        while True:
            for record in self.records:
                value = record.get("value") or {}
                key = record.get("key")
                if key == document_id and _is_signing_docs_for(value, document_id):
                    return value
                if _is_signing_docs_for(value, document_id):
                    return value
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.05)


def _is_signing_docs_for(value: dict[str, Any], document_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("messageName") != "SigningDocs":
        return False
    if value.get("applicationId") != document_id:
        return False
    return True


def assert_signing_docs_message(
    message: dict[str, Any],
    *,
    document_id: str,
) -> None:
    """Business assertions matching AKHQ screenshot / UMP contract."""
    assert message["applicationId"] == document_id
    assert message["correlationKey"] == f"{document_id}.NON_CREDIT_INSURANCE"
    assert message["messageName"] == "SigningDocs"
    assert "variables" in message
    assert message["variables"]["agreementLink"] == document_id


class LiveKafkaProbe:
    """Optional live consumer (enabled only when QA_LIVE_KAFKA=1)."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str | None = None,
    ) -> None:
        from confluent_kafka import Consumer, KafkaException  # noqa: F401

        self._KafkaException = KafkaException
        self.topic = topic
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id or f"qa-cms-links-{int(time.time())}",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._consumer.subscribe([topic])

    def find_signing_docs(
        self,
        *,
        document_id: str,
        timeout_sec: float = 30.0,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                continue
            try:
                value = json.loads(msg.value().decode("utf-8"))
            except (TypeError, ValueError, UnicodeDecodeError):
                continue
            key = msg.key().decode("utf-8") if msg.key() else None
            if predicate and not predicate(value):
                continue
            if key == document_id or _is_signing_docs_for(value, document_id):
                if _is_signing_docs_for(value, document_id):
                    return value
        return None

    def close(self) -> None:
        self._consumer.close()
