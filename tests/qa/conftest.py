"""Shared fixtures and config for CMS-links QA suite."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

load_dotenv(ROOT / ".env")


def _load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    return SCHEMAS


@pytest.fixture(scope="session")
def request_schema(schemas_dir: Path) -> dict:
    return _load_json(schemas_dir / "cms_links_request.schema.json")


@pytest.fixture(scope="session")
def response_schema(schemas_dir: Path) -> dict:
    return _load_json(schemas_dir / "cms_links_response.schema.json")


@pytest.fixture(scope="session")
def kafka_schema(schemas_dir: Path) -> dict:
    return _load_json(schemas_dir / "kafka_signing_docs.schema.json")


@pytest.fixture
def document_uuid() -> str:
    return os.getenv(
        "QA_DOCUMENT_UUID",
        "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )


@pytest.fixture
def alfacapture_cms_links_payload(document_uuid: str) -> dict:
    """Happy-path body for AlfaCapture2 flow (no url/itemId)."""
    return {
        "userId": os.getenv("QA_USER_ID", "XAGA56"),
        "systemName": os.getenv("QA_SYSTEM_NAME", "corpNcins"),
        "documents": [
            {
                "documentType": "agreement",
                "documentId": document_uuid,
                "alfaCaptureDocId": document_uuid,
            }
        ],
    }


@pytest.fixture
def expected_success_response(document_uuid: str) -> list[dict]:
    return [
        {
            "documentType": "agreement",
            "documentId": document_uuid,
            "resultCode": 0,
        }
    ]


@pytest.fixture
def expected_kafka_message(document_uuid: str) -> dict:
    return {
        "applicationId": document_uuid,
        "correlationKey": f"{document_uuid}.NON_CREDIT_INSURANCE",
        "messageName": "SigningDocs",
        "variables": {
            "agreementLink": document_uuid,
        },
    }


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.getenv(
        "QA_API_BASE_URL",
        "http://corp-gateway-test.moscow.alfaintra.net"
        "/corp-ncins-gateway/secure/corp-ncins-corp-ncins-api",
    )


@pytest.fixture(scope="session")
def api_headers() -> dict[str, str]:
    token = os.getenv("QA_BEARER_TOKEN", "")
    headers = {
        "a-channelid": os.getenv("QA_CHANNEL_ID", "nib"),
        "a-clienttype": os.getenv("QA_CLIENT_TYPE", "MOBILE"),
        "a-customerid": os.getenv("QA_CUSTOMER_ID", "123456"),
        "a-projectid": os.getenv("QA_PROJECT_ID", "corp-ncinsurance"),
        "a-userid": os.getenv("QA_A_USER_ID", "123456"),
        "content-type": "application/json",
        "sm-system-name": os.getenv("QA_SM_SYSTEM_NAME", "corp-ncins"),
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def kafka_bootstrap() -> str | None:
    return os.getenv("QA_KAFKA_BOOTSTRAP")


@pytest.fixture(scope="session")
def kafka_topic() -> str:
    return os.getenv("QA_KAFKA_TOPIC", "ump.process.from.system")


@pytest.fixture(scope="session")
def live_api_enabled() -> bool:
    return os.getenv("QA_LIVE_API", "").lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def live_kafka_enabled() -> bool:
    return os.getenv("QA_LIVE_KAFKA", "").lower() in {"1", "true", "yes"}
