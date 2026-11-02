from django.conf import settings
from django.db import models


class Machine(models.Model):
    machine_id = models.CharField(max_length=50, unique=True, blank=True)
    model = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=100)
    model_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "model_number")

    def save(self, *args, **kwargs):
        if not self.machine_id:
            self.machine_id = self.model or self.model_number
        if self.model and not self.model_number:
            self.model_number = self.model
        elif self.model_number and not self.model:
            self.model = self.model_number
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.model or self.model_number})"


class Manual(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="manuals")
    document_id = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=200)
    revision = models.CharField(max_length=50)
    pdf_file = models.FileField(upload_to="manuals/", blank=True)
    file = models.FileField(upload_to="manuals/", blank=True)
    page_count = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if not self.title:
            self.title = self.document_id
        if not self.document_id:
            self.document_id = self.title
        if self.pdf_file and not self.file:
            self.file = self.pdf_file
        elif self.file and not self.pdf_file:
            self.pdf_file = self.file
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document_id or self.title} rev {self.revision}"


class Passage(models.Model):
    manual = models.ForeignKey(Manual, on_delete=models.CASCADE, related_name="passages")
    machine_ref = models.ForeignKey(
        Machine, on_delete=models.CASCADE, related_name="passages", db_column="passage_machine_ref_id"
    )
    machine_id = models.CharField(max_length=50)
    document_id = models.CharField(max_length=100)
    revision = models.CharField(max_length=50)
    page_number = models.PositiveIntegerField()
    text = models.TextField()
    embedding_id = models.CharField(max_length=255, blank=True)
    embedding = models.JSONField(default=list)

    class Meta:
        indexes = [models.Index(fields=["machine_id"])]

    def __str__(self):
        return f"{self.document_id} p.{self.page_number}"


class QueryLog(models.Model):
    class Status(models.TextChoices):
        ANSWERED = "answered", "Answered"
        INSUFFICIENT_EVIDENCE = "insufficient_evidence", "Insufficient evidence"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="query_logs")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="query_logs")
    question = models.TextField()
    answer = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.INSUFFICIENT_EVIDENCE)
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.question[:60]}"


# Kept until ingestion and retrieval are migrated to Passage and QueryLog.
class Chunk(models.Model):
    manual = models.ForeignKey(Manual, on_delete=models.CASCADE, related_name="chunks")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="chunks")
    page_number = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField(default=list)

    class Meta:
        indexes = [models.Index(fields=["machine"])]


class Question(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    answer = models.TextField(blank=True)
    answered = models.BooleanField(default=False)
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
