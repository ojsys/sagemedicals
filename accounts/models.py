from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    HOSPITAL_ADMIN = "hospital_admin", "Hospital Administrator"
    DOCTOR = "doctor", "Doctor / Consultant"
    RESIDENT = "resident", "Resident / House Officer"
    NURSE = "nurse", "Nurse"
    LAB_TECH = "lab_tech", "Lab Technician / Scientist"
    RADIOLOGIST = "radiologist", "Radiologist / Imaging Tech"
    PHARMACIST = "pharmacist", "Pharmacist"
    BILLING_OFFICER = "billing_officer", "Billing Officer"
    RECEPTIONIST = "receptionist", "Receptionist"
    RECORDS_OFFICER = "records_officer", "Records Officer"
    PATIENT = "patient", "Patient"
    AUDITOR = "auditor", "Auditor"


CLINICAL_ROLES = {
    Role.DOCTOR,
    Role.RESIDENT,
    Role.NURSE,
    Role.LAB_TECH,
    Role.RADIOLOGIST,
    Role.PHARMACIST,
}


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.SUPER_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.PATIENT)
    department = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_lead_doctor = models.BooleanField(
        default=False,
        help_text="Lead Doctor — granted by Super Admin. Can create and manage staff users from the application.",
    )
    date_joined = models.DateTimeField(default=timezone.now)
    # Time-bound delegation
    delegate_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="delegated_from"
    )
    delegation_expires_at = models.DateTimeField(null=True, blank=True)
    # Password policy
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_clinical(self):
        return self.role in CLINICAL_ROLES

    @property
    def can_manage_staff(self):
        """True for the platform Super Admin or any user granted Lead Doctor rights."""
        return bool(
            self.is_superuser
            or self.role == Role.SUPER_ADMIN
            or self.is_lead_doctor
        )

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def record_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def reset_login_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])


class AuditLog(models.Model):
    """Append-only audit trail for every clinical read and write."""

    ACTION_READ = "read"
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_BREAK_GLASS = "break_glass"
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"

    ACTION_CHOICES = [
        (ACTION_READ, "Read"),
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_BREAK_GLASS, "Break-the-Glass"),
        (ACTION_LOGIN, "Login"),
        (ACTION_LOGOUT, "Logout"),
    ]

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    app_label = models.CharField(max_length=50, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["app_label", "model_name", "object_id"]),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name}:{self.object_id} @ {self.timestamp}"
