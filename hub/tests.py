import hashlib
import hmac
import json
import time
from unittest.mock import patch
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import encode_multipart

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Designer, DesignerRating, HubAdminUser, HubBrief, SiteNode
from .portal_admin import ADMIN_SESSION_KEY


class _MockHttpResponse:
    def __init__(self, content: bytes = b"solid test"):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        return None


class HubApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = SiteNode.objects.create(
            site_id="site-1",
            name="Workshop 1",
            callback_base_url="https://example.test",
            site_token="token-123",
            site_secret="secret-456",
        )

    def _signed_headers(self, body: dict):
        timestamp = str(int(time.time()))
        raw_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        signature = hmac.new(
            self.site.site_secret.encode("utf-8"),
            f"{timestamp}\n{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "HTTP_AUTHORIZATION": f"Bearer {self.site.site_token}",
            "HTTP_X_SITE_ID": self.site.site_id,
            "HTTP_X_TIMESTAMP": timestamp,
            "HTTP_X_SIGNATURE": signature,
        }, raw_body

    def _signed_headers_raw(self, raw_body: bytes):
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.site.site_secret.encode("utf-8"),
            f"{timestamp}\n".encode("utf-8") + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "HTTP_AUTHORIZATION": f"Bearer {self.site.site_token}",
            "HTTP_X_SITE_ID": self.site.site_id,
            "HTTP_X_TIMESTAMP": timestamp,
            "HTTP_X_SIGNATURE": signature,
        }

    def test_create_brief_with_hmac(self):
        payload = {
            "local_brief_id": 12,
            "brief_number": "3D-000001",
            "client_ref": "5",
            "model_url": "https://example.test/model",
            "description": "ТЗ",
            "agreed_price": "5000.00",
            "designer_share_amount": "3500.00",
            "site_share_amount": "1500.00",
            "has_stl": True,
            "screenshots_count": 2,
        }
        headers, raw_body = self._signed_headers(payload)
        with patch("hub.services.requests.get", return_value=_MockHttpResponse(b"solid payload")):
            response = self.client.generic(
                "POST",
                "/api/v1/briefs",
                data=raw_body,
                content_type="application/json",
                **headers,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], HubBrief.Status.QUEUED)
        brief = HubBrief.objects.get(site=self.site, local_brief_id=12)
        self.assertTrue(bool(brief.source_stl_file))

    def test_create_brief_invalid_signature(self):
        payload = {
            "local_brief_id": 12,
            "brief_number": "3D-000001",
            "client_ref": "5",
            "agreed_price": "5000.00",
            "designer_share_amount": "3500.00",
            "site_share_amount": "1500.00",
        }
        headers, raw_body = self._signed_headers(payload)
        headers["HTTP_X_SIGNATURE"] = "bad-signature"
        response = self.client.generic(
            "POST",
            "/api/v1/briefs",
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 401)

    def test_update_keeps_existing_model_url_when_not_provided(self):
        create_payload = {
            "local_brief_id": 21,
            "brief_number": "3D-000021",
            "client_ref": "11",
            "model_url": "https://example.test/source.stl",
            "description": "Исходный вариант",
            "agreed_price": "5000.00",
            "designer_share_amount": "3500.00",
            "site_share_amount": "1500.00",
            "has_stl": True,
            "screenshots_count": 2,
        }
        headers, raw_body = self._signed_headers(create_payload)
        with patch("hub.services.requests.get", return_value=_MockHttpResponse()):
            create_response = self.client.generic(
                "POST",
                "/api/v1/briefs",
                data=raw_body,
                content_type="application/json",
                **headers,
            )
        self.assertEqual(create_response.status_code, 200)
        brief_id = create_response.data["brief_id"]

        update_payload = {
            "local_brief_id": 21,
            "brief_number": "3D-000021",
            "client_ref": "11",
            "description": "Обновленное описание",
            "agreed_price": "5100.00",
            "designer_share_amount": "3570.00",
            "site_share_amount": "1530.00",
        }
        headers, raw_body = self._signed_headers(update_payload)
        with patch("hub.services.requests.get", return_value=_MockHttpResponse()):
            update_response = self.client.generic(
                "POST",
                f"/api/v1/briefs/{brief_id}",
                data=raw_body,
                content_type="application/json",
                **headers,
            )
        self.assertEqual(update_response.status_code, 200)
        brief = HubBrief.objects.get(public_id=brief_id)
        self.assertEqual(brief.model_url, "https://example.test/source.stl")

    def test_upload_source_stl_multipart(self):
        create_payload = {
            "local_brief_id": 31,
            "brief_number": "3D-000031",
            "client_ref": "31",
            "description": "Тест STL upload",
            "agreed_price": "5000.00",
            "designer_share_amount": "3500.00",
            "site_share_amount": "1500.00",
        }
        headers, raw_body = self._signed_headers(create_payload)
        create_response = self.client.generic(
            "POST",
            "/api/v1/briefs",
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(create_response.status_code, 200)
        brief_id = create_response.data["brief_id"]

        boundary = "BoUnDaRyStRiNg"
        body = encode_multipart(
            boundary,
            {
                "file": SimpleUploadedFile("model.stl", b"solid test-model", content_type="model/stl"),
            },
        )
        upload_headers = self._signed_headers_raw(body)
        upload_response = self.client.generic(
            "POST",
            f"/api/v1/briefs/{brief_id}/source-stl",
            data=body,
            content_type=f"multipart/form-data; boundary={boundary}",
            **upload_headers,
        )
        self.assertEqual(upload_response.status_code, 200)
        brief = HubBrief.objects.get(public_id=brief_id)
        self.assertTrue(bool(brief.source_stl_file))
        self.assertTrue(brief.has_stl)


class MaxBotWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = SiteNode.objects.create(
            site_id="site-1",
            name="Workshop 1",
            callback_base_url="https://example.test",
            site_token="token-123",
            site_secret="secret-456",
        )
        self.brief = HubBrief.objects.create(
            public_id="brief-1",
            site=self.site,
            local_brief_id=88,
            brief_number="3D-000088",
            client_ref="cl-88",
            agreed_price="4000.00",
            designer_share_amount="2800.00",
            site_share_amount="1200.00",
            status=HubBrief.Status.QUEUED,
        )

    def _send_bot(self, text: str, user_id: str = "max-1") -> str:
        response = self.client.post(
            "/api/v1/max/webhook",
            {"user_id": user_id, "text": text},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.data["reply"]

    def test_designer_registration_and_assign(self):
        self.assertIn("Введите ФИО", self._send_bot("Регистрация: Дизайнер"))
        self.assertIn("телефон СБП", self._send_bot("Иван Иванов"))
        self.assertIn("Опишите ваш опыт", self._send_bot("+79991112233"))
        self.assertIn("ссылку на портфолио", self._send_bot("2 года CAD"))
        self.assertIn("Регистрация завершена", self._send_bot("https://portfolio.example"))

        self.assertTrue(Designer.objects.filter(max_user_id="max-1").exists())
        queue_reply = self._send_bot("Очередь")
        self.assertIn("brief-1", queue_reply)

        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            take_reply = self._send_bot("Беру brief-1 2 дня")
        self.assertIn("назначена", take_reply.lower())
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.status, HubBrief.Status.ASSIGNED)
        self.assertEqual(self.brief.designer.max_user_id, "max-1")


class DesignerWebQueueTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = SiteNode.objects.create(
            site_id="site-2",
            name="Workshop 2",
            callback_base_url="https://example.test",
            site_token="token-abc",
            site_secret="secret-def",
        )
        self.designer_1 = Designer.objects.create(
            max_user_id="mx-1",
            full_name="Анна Дизайнер",
            sbp_phone="+79990000001",
            experience_text="3 года",
            portfolio_url="https://portfolio1.example",
            web_login="anna",
            web_password_hash=make_password("pass-anna"),
        )
        self.designer_2 = Designer.objects.create(
            max_user_id="mx-2",
            full_name="Игорь Дизайнер",
            sbp_phone="+79990000002",
            experience_text="2 года",
            portfolio_url="https://portfolio2.example",
            web_login="igor",
            web_password_hash=make_password("pass-igor"),
        )
        self.brief = HubBrief.objects.create(
            public_id="brief-web-1",
            site=self.site,
            local_brief_id=55,
            brief_number="3D-000055",
            client_ref="client-55",
            agreed_price="6000.00",
            designer_share_amount="4200.00",
            site_share_amount="1800.00",
            status=HubBrief.Status.QUEUED,
        )

    def _login(self, login: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/designer/auth/login",
            {"login": login, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.data["token"]

    def test_queue_visible_and_claim_locked(self):
        token_1 = self._login("anna", "pass-anna")
        response = self.client.get(
            "/api/v1/designer/briefs",
            HTTP_AUTHORIZATION=f"Bearer {token_1}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], HubBrief.Status.QUEUED)
        self.assertIsNone(response.data["results"][0]["designer_name"])

        claim_response_1 = self.client.post(
            "/api/v1/designer/briefs/brief-web-1/claim",
            {"eta": "48 часов"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token_1}",
        )
        self.assertEqual(claim_response_1.status_code, 200)

        token_2 = self._login("igor", "pass-igor")
        claim_response_2 = self.client.post(
            "/api/v1/designer/briefs/brief-web-1/claim",
            {"eta": "24 часа"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token_2}",
        )
        self.assertEqual(claim_response_2.status_code, 409)
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.designer, self.designer_1)


class DesignerBootstrapPortalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = SiteNode.objects.create(
            site_id="site-3",
            name="Workshop 3",
            callback_base_url="https://example.test",
            site_token="token-z",
            site_secret="secret-z",
        )
        self.designer = Designer.objects.create(
            max_user_id="mx-3",
            full_name="Павел Дизайнер",
            sbp_phone="+79990000003",
            experience_text="4 года",
            portfolio_url="https://portfolio3.example",
            web_login="pavel",
            web_password_hash=make_password("pass-pavel"),
        )
        self.brief = HubBrief.objects.create(
            public_id="brief-web-portal",
            site=self.site,
            local_brief_id=56,
            brief_number="3D-000056",
            client_ref="client-56",
            agreed_price="6500.00",
            designer_share_amount="4550.00",
            site_share_amount="1950.00",
            status=HubBrief.Status.QUEUED,
        )

    def test_login_and_claim_via_bootstrap_pages(self):
        login_get = self.client.get("/designer/login")
        self.assertEqual(login_get.status_code, 200)

        login_post = self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        self.assertEqual(login_post.status_code, 302)
        self.assertEqual(login_post.url, "/designer/queue")

        queue = self.client.get("/designer/queue")
        self.assertEqual(queue.status_code, 200)
        self.assertContains(queue, "Свободные задачи")
        self.assertContains(queue, "brief-web-portal")

        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            claim = self.client.post("/designer/briefs/brief-web-portal/claim", {"eta": "3 дня"})
        self.assertEqual(claim.status_code, 302)
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.designer, self.designer)
        self.assertEqual(self.brief.status, HubBrief.Status.ASSIGNED)

    def test_claim_directly_from_brief_detail_page(self):
        self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            response = self.client.post(
                "/designer/briefs/brief-web-portal/claim",
                {
                    "eta": "5 дней",
                    "next": "/designer/briefs/brief-web-portal",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/designer/briefs/brief-web-portal")
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.designer, self.designer)

    def test_assigned_designer_can_update_status_and_artifacts(self):
        self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            self.client.post("/designer/briefs/brief-web-portal/claim", {"eta": "3 дня"})

        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            update = self.client.post(
                "/designer/briefs/brief-web-portal/update",
                {
                    "status": HubBrief.Status.DONE,
                    "designer_comment": "Готово, все размеры проверены.",
                    "final_model_url": "https://files.example/final-model.stl",
                    "final_screenshots_urls": "https://files.example/screen-1.png\nhttps://files.example/screen-2.png",
                },
            )
        self.assertEqual(update.status_code, 302)

        self.brief.refresh_from_db()
        self.assertEqual(self.brief.status, HubBrief.Status.DONE)
        self.assertEqual(self.brief.designer_comment, "Готово, все размеры проверены.")
        self.assertEqual(self.brief.final_model_url, "https://files.example/final-model.stl")
        self.assertIn("screen-2.png", self.brief.final_screenshots_urls)

    def test_done_status_with_uploaded_files(self):
        self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            self.client.post("/designer/briefs/brief-web-portal/claim", {"eta": "3 дня"})

        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            update = self.client.post(
                "/designer/briefs/brief-web-portal/update",
                {
                    "status": HubBrief.Status.DONE,
                    "designer_comment": "Готово через загрузку файлов.",
                    "final_model_url": "",
                    "final_screenshots_urls": "",
                    "final_model_file": SimpleUploadedFile("final.stl", b"solid final"),
                    "final_screenshots_archive": SimpleUploadedFile("shots.zip", b"PK\x03\x04"),
                },
            )
        self.assertEqual(update.status_code, 302)
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.status, HubBrief.Status.DONE)
        self.assertTrue(bool(self.brief.final_model_file))
        self.assertTrue(bool(self.brief.final_screenshots_archive))
        self.assertGreaterEqual(mock_post.call_count, 1)
        last_payload = json.loads(mock_post.call_args.kwargs["data"].decode("utf-8"))
        self.assertEqual(last_payload["event"], "done")

    def test_done_status_requires_artifacts(self):
        self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            self.client.post("/designer/briefs/brief-web-portal/claim", {"eta": "3 дня"})

        update = self.client.post(
            "/designer/briefs/brief-web-portal/update",
            {
                "status": HubBrief.Status.DONE,
                "designer_comment": "Без файлов",
                "final_model_url": "",
                "final_screenshots_urls": "",
            },
            follow=True,
        )
        self.assertEqual(update.status_code, 200)
        self.brief.refresh_from_db()
        self.assertEqual(self.brief.status, HubBrief.Status.ASSIGNED)

    def test_in_progress_update_sends_webhook_with_comment(self):
        self.client.post("/designer/login", {"login": "pavel", "password": "pass-pavel"})
        with patch("hub.services.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            self.client.post("/designer/briefs/brief-web-portal/claim", {"eta": "3 дня"})
            self.client.post(
                "/designer/briefs/brief-web-portal/update",
                {
                    "status": HubBrief.Status.IN_PROGRESS,
                    "designer_comment": "Начал моделирование, ETA 2 дня.",
                    "final_model_url": "",
                    "final_screenshots_urls": "",
                },
            )
            self.assertGreaterEqual(mock_post.call_count, 2)
            last_payload = json.loads(mock_post.call_args.kwargs["data"].decode("utf-8"))
            self.assertEqual(last_payload["event"], "in_progress")
            self.assertEqual(last_payload["message"], "Начал моделирование, ETA 2 дня.")


class DesignerRatingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = SiteNode.objects.create(
            site_id="site-rate",
            name="Workshop Rate",
            callback_base_url="https://example.test",
            site_token="token-rate",
            site_secret="secret-rate",
        )
        self.designer = Designer.objects.create(
            max_user_id="d-rate-1",
            full_name="Рейтинг Дизайнер",
            sbp_phone="79001112233",
            experience_text="exp",
            portfolio_url="https://example.test/p",
            web_login="rater",
            web_password_hash=make_password("pass"),
            is_active=True,
        )
        self.brief = HubBrief.objects.create(
            public_id="brief-rate-1",
            site=self.site,
            local_brief_id=77,
            brief_number="3D-000077",
            client_ref="c-77",
            agreed_price="5000.00",
            designer_share_amount="3500.00",
            site_share_amount="1500.00",
            status=HubBrief.Status.DONE,
            designer=self.designer,
        )

    def _signed(self, body: dict):
        timestamp = str(int(time.time()))
        raw_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        signature = hmac.new(
            self.site.site_secret.encode("utf-8"),
            f"{timestamp}\n{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "HTTP_AUTHORIZATION": f"Bearer {self.site.site_token}",
            "HTTP_X_SITE_ID": self.site.site_id,
            "HTTP_X_TIMESTAMP": timestamp,
            "HTTP_X_SIGNATURE": signature,
        }, raw_body

    def test_create_rating_updates_designer_avg(self):
        payload = {
            "event_id": "rating-77-1",
            "score": 5,
            "comment": "Отлично",
            "rated_by": "Менеджер",
            "local_brief_id": 77,
        }
        headers, raw_body = self._signed(payload)
        response = self.client.generic(
            "POST",
            "/api/v1/briefs/brief-rate-1/ratings",
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "created")
        self.assertEqual(response.data["score"], 5)
        self.designer.refresh_from_db()
        self.assertEqual(self.designer.ratings_count, 1)
        self.assertEqual(str(self.designer.avg_rating), "5.00")

        headers, raw_body = self._signed(payload)
        dup = self.client.generic(
            "POST",
            "/api/v1/briefs/brief-rate-1/ratings",
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(dup.status_code, 200)
        self.assertEqual(dup.data["status"], "duplicate")
        self.assertEqual(DesignerRating.objects.count(), 1)

    def test_rating_requires_assigned_designer(self):
        self.brief.designer = None
        self.brief.save(update_fields=["designer"])
        payload = {"event_id": "rating-orphan", "score": 4}
        headers, raw_body = self._signed(payload)
        response = self.client.generic(
            "POST",
            "/api/v1/briefs/brief-rate-1/ratings",
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)


class PortalAdminWebTests(TestCase):
    def setUp(self):
        self.admin = HubAdminUser.objects.create(
            full_name="Админ",
            web_login="padmin",
            web_password_hash=make_password("admin-pass"),
            is_active=True,
        )
        self.site = SiteNode.objects.create(
            site_id="site-admin",
            name="Workshop Admin",
            callback_base_url="https://example.test",
            site_token="t",
            site_secret="s",
        )
        self.designer = Designer.objects.create(
            max_user_id="d-admin-1",
            full_name="Удаляемый",
            sbp_phone="7900",
            experience_text="e",
            portfolio_url="https://example.test/p",
            web_login="victim",
            web_password_hash=make_password("x"),
            is_active=True,
        )
        self.brief = HubBrief.objects.create(
            public_id="brief-admin-del",
            site=self.site,
            local_brief_id=9,
            brief_number="3D-9",
            client_ref="c9",
            agreed_price="1000.00",
            designer_share_amount="700.00",
            site_share_amount="300.00",
            status=HubBrief.Status.QUEUED,
        )

    def _login(self):
        response = self.client.post(
            "/portal-admin/login",
            {"login": "padmin", "password": "admin-pass"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get(ADMIN_SESSION_KEY), self.admin.id)

    def test_admin_dashboard_and_issue_account(self):
        self._login()
        dash = self.client.get("/portal-admin/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "Рейтинг дизайнеров")

        created = self.client.post(
            "/portal-admin/designers/create",
            {
                "full_name": "Новый Дизайнер",
                "web_login": "newbie",
                "password": "secret12",
                "sbp_phone": "79005554433",
            },
        )
        self.assertEqual(created.status_code, 302)
        self.assertTrue(Designer.objects.filter(web_login="newbie").exists())

    def test_admin_deactivate_and_delete_user(self):
        self._login()
        toggle = self.client.post(f"/portal-admin/designers/{self.designer.id}/toggle")
        self.assertEqual(toggle.status_code, 302)
        self.designer.refresh_from_db()
        self.assertFalse(self.designer.is_active)

        delete = self.client.post(f"/portal-admin/designers/{self.designer.id}/delete")
        self.assertEqual(delete.status_code, 302)
        self.assertFalse(Designer.objects.filter(id=self.designer.id).exists())

    def test_admin_delete_brief(self):
        self._login()
        delete = self.client.post(f"/portal-admin/briefs/{self.brief.public_id}/delete")
        self.assertEqual(delete.status_code, 302)
        self.assertFalse(HubBrief.objects.filter(public_id="brief-admin-del").exists())
