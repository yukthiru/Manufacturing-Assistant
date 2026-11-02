import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Chunk, Machine, Manual, Question
from .roles import ADMIN, ENGINEER, SUPERVISOR
from .samples import LATHE_MAINTENANCE, PRESS_MAINTENANCE, make_pdf


class BaseCase(APITestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        ctx = override_settings(MEDIA_ROOT=tmp, LLM_API_KEY="", RAG_MIN_SCORE=0.2)
        ctx.enable()
        self.addCleanup(ctx.disable)
        self.addCleanup(shutil.rmtree, tmp, True)
        self.admin = self.mk("admin1", ADMIN)
        self.engineer = self.mk("eng1", ENGINEER)
        self.engineer2 = self.mk("eng2", ENGINEER)
        self.supervisor = self.mk("sup1", SUPERVISOR)
        self.press = Machine.objects.create(name="Hydraulic Press", model_number="HP-200")
        self.lathe = Machine.objects.create(name="CNC Lathe", model_number="CL-50")

    def mk(self, username, role):
        user = User.objects.create_user(username, password="pw")
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

    def upload(self, user, machine, pages, title="Manual", revision="A", name="m.pdf", content=None):
        self.client.force_authenticate(user)
        f = SimpleUploadedFile(name, content or make_pdf(pages), content_type="application/pdf")
        return self.client.post("/api/manuals/", {"machine": machine.id, "title": title,
                                                  "revision": revision, "file": f}, format="multipart")

    def load_manuals(self):
        self.assertEqual(self.upload(self.admin, self.press, PRESS_MAINTENANCE, "HP-200 Maintenance", "B").status_code, 201)
        self.assertEqual(self.upload(self.admin, self.lathe, LATHE_MAINTENANCE, "CL-50 Maintenance", "C").status_code, 201)

    def ask(self, user, machine, question):
        self.client.force_authenticate(user)
        return self.client.post("/api/ask/", {"machine": machine.id, "question": question}, format="json")


class AccessControlTests(BaseCase):
    def test_engineer_cannot_upload_manual(self):
        resp = self.upload(self.engineer, self.press, PRESS_MAINTENANCE, content=b"%PDF-")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Manual.objects.count(), 0)

    def test_supervisor_cannot_upload_or_create_machine(self):
        self.assertEqual(
            self.upload(self.supervisor, self.press, PRESS_MAINTENANCE, content=b"%PDF-").status_code,
            403,
        )
        self.client.force_authenticate(self.supervisor)
        resp = self.client.post("/api/machines/", {"name": "X", "model_number": "1"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_is_rejected(self):
        self.assertIn(self.client.get("/api/machines/").status_code, (401, 403))

    def test_supervisor_and_admin_cannot_ask(self):
        self.load_manuals()
        self.assertEqual(self.ask(self.supervisor, self.press, "oil filter?").status_code, 403)

    def test_invalid_file_rejected(self):
        resp = self.upload(self.admin, self.press, None, name="fake.pdf", content=b"not a pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Manual.objects.count(), 0)


class RetrievalTests(BaseCase):
    def test_admin_upload_indexes_pages(self):
        from . import rag

        self.load_manuals()
        pages = set(Chunk.objects.filter(machine=self.press).values_list("page_number", flat=True))
        self.assertEqual(pages, {1, 2})

    def test_retrieval_excludes_other_machines_passages(self):
        from . import rag

        self.load_manuals()
        hits = rag.retrieve(self.press, "How often should the spindle bearing grease be replaced?", k=10)
        self.assertTrue(hits)
        self.assertTrue(all(c.machine_id == self.press.id for c, _ in hits))

    def test_question_only_in_other_machine_manual_is_unanswered(self):
        from . import rag

        self.load_manuals()
        resp = self.ask(self.engineer, self.press, "How often should the spindle bearings be greased?")
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["answered"])
        self.assertEqual(resp.data["sources"], [])
        self.assertEqual(resp.data["answer"], rag.NO_INFO)

    def test_answerable_question_cites_manual_revision_and_page(self):
        from . import rag

        self.load_manuals()
        resp = self.ask(self.engineer, self.press, "How often do I replace the hydraulic oil filter?")
        self.assertTrue(resp.data["answered"])
        top = resp.data["sources"][0]
        self.assertEqual((top["manual_title"], top["revision"], top["page"]), ("HP-200 Maintenance", "B", 2))
        self.assertIn("500", top["passage"])

    def test_unsupported_question_is_unanswered(self):
        from . import rag

        self.load_manuals()
        resp = self.ask(self.engineer, self.press, "What is the cafeteria menu on Friday?")
        self.assertFalse(resp.data["answered"])


class HistoryTests(BaseCase):
    def test_history_persists_and_is_role_scoped(self):
        self.load_manuals()
        self.ask(self.engineer, self.press, "How often do I replace the hydraulic oil filter?")
        self.ask(self.engineer2, self.press, "What is the cafeteria menu?")
        self.assertEqual(Question.objects.count(), 2)

        self.client.force_authenticate(self.engineer)
        self.assertEqual(len(self.client.get("/api/questions/").data), 1)

        self.client.force_authenticate(self.supervisor)
        self.assertEqual(len(self.client.get("/api/questions/").data), 2)
        unanswered = self.client.get("/api/questions/?unanswered=1").data
        self.assertEqual(len(unanswered), 1)
        self.assertEqual(self.client.post("/api/questions/", {}, format="json").status_code, 405)
