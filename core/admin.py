from django.contrib import admin
from .models import Machine, Manual, Passage, QueryLog, Question


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("machine_id", "model", "name")


@admin.register(Manual)
class ManualAdmin(admin.ModelAdmin):
    list_display = ("document_id", "machine", "revision", "page_count", "uploaded_at")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "machine", "user", "answered", "created_at")
    list_filter = ("answered", "machine")


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ("document_id", "machine_id", "revision", "page_number")
    list_filter = ("machine_id", "document_id", "revision")


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("question", "machine", "user", "status", "created_at")
    list_filter = ("status", "machine")
    readonly_fields = ("user", "machine", "question", "answer", "status", "sources", "created_at")
