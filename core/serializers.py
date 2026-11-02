from rest_framework import serializers

from .models import Machine, Manual, Question


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ["id", "machine_id", "model", "name", "model_number", "description"]


class ManualSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source="machine.name", read_only=True)
    uploaded_by = serializers.CharField(source="uploaded_by.username", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Manual
        fields = ["id", "machine", "machine_name", "document_id", "title", "revision",
                  "pdf_file", "file", "file_url", "page_count", "uploaded_by", "uploaded_at"]
        read_only_fields = ["page_count", "uploaded_at"]
        extra_kwargs = {
            "title": {"required": False},
            "document_id": {"required": False},
            "pdf_file": {"required": False, "write_only": True},
            "file": {"required": False, "write_only": True},
        }

    def validate(self, attrs):
        if not (attrs.get("document_id") or attrs.get("title")):
            raise serializers.ValidationError(
                {"document_id": "Provide a document ID."}
            )
        if not (attrs.get("pdf_file") or attrs.get("file")):
            raise serializers.ValidationError(
                {"pdf_file": "Provide a PDF file."}
            )
        return attrs

    def get_file_url(self, obj):
        return f"/api/manuals/{obj.pk}/file/"

    def validate_file(self, f):
        head = f.read(5)
        f.seek(0)
        if not f.name.lower().endswith(".pdf") or head != b"%PDF-":
            raise serializers.ValidationError("Only valid PDF files are accepted.")
        return f

    def validate_pdf_file(self, f):
        head = f.read(5)
        f.seek(0)
        if not f.name.lower().endswith(".pdf") or head != b"%PDF-":
            raise serializers.ValidationError("Only valid PDF files are accepted.")
        return f


class QuestionSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source="machine.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Question
        fields = ["id", "machine", "machine_name", "username", "text", "answer", "answered",
                  "sources", "created_at"]
        read_only_fields = fields


class AskSerializer(serializers.Serializer):
    machine = serializers.PrimaryKeyRelatedField(queryset=Machine.objects.all())
    question = serializers.CharField(max_length=1000)
