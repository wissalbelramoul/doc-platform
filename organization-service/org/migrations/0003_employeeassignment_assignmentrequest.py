from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("org", "0002_documentcountprojection_organizationalresponsibility_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField()),
                ("role", models.CharField(choices=[("DOS", "Directeur des Opérations"), ("DES", "Directeur Engineering"), ("DO", "Directeur Opérationnel"), ("DE", "Directeur Engineering"), ("DA", "Directeur Adjoint"), ("CS", "Chef de Service")], max_length=3)),
                ("reports_to_user_id", models.UUIDField(blank=True, null=True)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="employee_assignments", to="org.organizationalunit")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["unit", "role", "ended_at"], name="org_employee__unit_id_7c9262_idx"),
                    models.Index(fields=["user_id"], name="org_employee__user_id_7e4f45_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="employeeassignment",
            constraint=models.UniqueConstraint(condition=models.Q(("ended_at__isnull", True)), fields=("user_id", "role", "unit", "ended_at"), name="unique_active_assignment_per_user_role_unit"),
        ),
        migrations.CreateModel(
            name="AssignmentRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("requester_user_id", models.UUIDField()),
                ("target_user_id", models.UUIDField()),
                ("role", models.CharField(choices=[("DOS", "Directeur des Opérations"), ("DES", "Directeur Engineering"), ("DO", "Directeur Opérationnel"), ("DE", "Directeur Engineering"), ("DA", "Directeur Adjoint"), ("CS", "Chef de Service")], max_length=3)),
                ("reports_to_user_id", models.UUIDField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("PENDING", "En attente"), ("APPROVED", "Approuvée"), ("REJECTED", "Rejetée")], default="PENDING", max_length=20)),
                ("reviewed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assignment_requests", to="org.organizationalunit")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="org_assignme_status_cd4b5b_idx"),
                    models.Index(fields=["target_user_id"], name="org_assignme_target__b93fd2_idx"),
                ],
            },
        ),
    ]
