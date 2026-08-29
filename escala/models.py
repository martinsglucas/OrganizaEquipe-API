import uuid
import secrets
import string
from django.db import models
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if email is None:
            raise TypeError('Usuários devem ter um email.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        if password is None:
            raise TypeError('Superusuários devem ter uma senha.')
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True) 
    email = models.EmailField(max_length=100, unique=True) 
    username = models.CharField(max_length=100, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    fcm_token = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.first_name


class PushSubscription(models.Model):
    PERMISSION_DEFAULT = "default"
    PERMISSION_GRANTED = "granted"
    PERMISSION_DENIED = "denied"
    PERMISSION_CHOICES = [
        (PERMISSION_DEFAULT, "Default"),
        (PERMISSION_GRANTED, "Granted"),
        (PERMISSION_DENIED, "Denied"),
    ]

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    device_label = models.CharField(max_length=150, blank=True)
    is_ios = models.BooleanField(default=False)
    is_standalone = models.BooleanField(default=False)
    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default=PERMISSION_DEFAULT,
    )
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at", "-updated_at"]

    def __str__(self):
        return f"{self.user.email} - {self.device_label or self.platform or 'device'}"

def generate_unique_access_code():
    while True:
        code = uuid.uuid4().hex[:6].upper()
        if not (Team.objects.filter(code_access=code).exists() or Organization.objects.filter(code_access=code).exists()):
            return code

class Organization(models.Model):
    name = models.CharField(max_length=100)
    admins = models.ManyToManyField('User', related_name='administered_organizations')
    members = models.ManyToManyField('User', related_name='organizations')
    code_access = models.CharField(max_length=6, default=generate_unique_access_code, unique=True)

    def __str__(self):
        return self.name


class OrganizationCreationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovada'
        REJECTED = 'rejected', 'Rejeitada'

    requester = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='organization_creation_requests',
    )
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    organization = models.OneToOneField(
        'Organization',
        on_delete=models.SET_NULL,
        related_name='creation_request',
        blank=True,
        null=True,
    )
    reviewed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='reviewed_organization_creation_requests',
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['requester', 'name'],
                condition=models.Q(status='pending'),
                name='unique_pending_organization_request',
            ),
        ]

    def __str__(self):
        return f'{self.requester} solicita criar {self.name}'

    @transaction.atomic
    def approve(self, reviewer):
        creation_request = type(self).objects.select_for_update().get(pk=self.pk)
        if creation_request.status == self.Status.APPROVED:
            return creation_request.organization
        if creation_request.status != self.Status.PENDING:
            raise ValidationError('Somente solicitações pendentes podem ser aprovadas.')

        organization = Organization.objects.create(name=creation_request.name)
        organization.admins.add(creation_request.requester)
        organization.members.add(creation_request.requester)
        creation_request.status = self.Status.APPROVED
        creation_request.organization = organization
        creation_request.reviewed_by = reviewer
        creation_request.reviewed_at = timezone.now()
        creation_request.save(
            update_fields=['status', 'organization', 'reviewed_by', 'reviewed_at', 'updated_at'],
        )
        self.organization = organization
        self.status = creation_request.status
        return organization

    @transaction.atomic
    def reject(self, reviewer):
        creation_request = type(self).objects.select_for_update().get(pk=self.pk)
        if creation_request.status == self.Status.REJECTED:
            return
        if creation_request.status != self.Status.PENDING:
            raise ValidationError('Somente solicitações pendentes podem ser rejeitadas.')

        creation_request.status = self.Status.REJECTED
        creation_request.reviewed_by = reviewer
        creation_request.reviewed_at = timezone.now()
        creation_request.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'],
        )
        self.status = creation_request.status

class Team(models.Model):
    class Visibility(models.TextChoices):
        DISCOVERABLE = 'discoverable', 'Descoberta'
        PRIVATE = 'private', 'Privada'
        CLOSED = 'closed', 'Fechada'

    name = models.CharField(max_length=100)
    admins = models.ManyToManyField('User', related_name='administered_teams')
    code_access = models.CharField(max_length=6, default=generate_unique_access_code, unique=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='teams')
    members = models.ManyToManyField('User', related_name='teams')
    visibility = models.CharField(
        max_length=12,
        choices=Visibility.choices,
        default=Visibility.DISCOVERABLE,
    )

    def __str__(self):
        return self.name


def generate_invitation_link_token():
    return ''.join(secrets.choice(string.ascii_letters) for _ in range(48))


class InvitationLink(models.Model):
    organization = models.OneToOneField(
        'Organization',
        on_delete=models.CASCADE,
        related_name='invitation_link',
        blank=True,
        null=True,
    )
    team = models.OneToOneField(
        'Team',
        on_delete=models.CASCADE,
        related_name='invitation_link',
        blank=True,
        null=True,
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_invitation_link_token,
    )
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='created_invitation_links',
        blank=True,
        null=True,
    )
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization__isnull=False, team__isnull=True)
                    | models.Q(organization__isnull=True, team__isnull=False)
                ),
                name='invitation_link_has_one_target',
            ),
        ]

    @property
    def target(self):
        return self.organization or self.team

    @property
    def target_type(self):
        return 'organization' if self.organization_id else 'team'

    @property
    def is_active(self):
        return self.revoked_at is None and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    @property
    def status(self):
        if self.revoked_at is not None:
            return 'revoked'
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return 'expired'
        return 'active'

    def __str__(self):
        return f'{self.target_type}: {self.target}'


class TeamJoinRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovada'
        REJECTED = 'rejected', 'Rejeitada'

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='team_join_requests',
    )
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
        related_name='join_requests',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='reviewed_team_join_requests',
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'team'],
                condition=models.Q(status='pending'),
                name='unique_pending_team_join_request',
            ),
        ]

    def __str__(self):
        return f'{self.user} solicita ingressar em {self.team}'

    @transaction.atomic
    def approve(self, reviewer):
        join_request = type(self).objects.select_for_update().get(pk=self.pk)
        if join_request.status == self.Status.APPROVED:
            return
        if join_request.status != self.Status.PENDING:
            raise ValidationError('Somente solicitações pendentes podem ser aprovadas.')

        join_request.team.members.add(join_request.user)
        join_request.status = self.Status.APPROVED
        join_request.reviewed_by = reviewer
        join_request.reviewed_at = timezone.now()
        join_request.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'],
        )
        self.status = join_request.status

    @transaction.atomic
    def reject(self, reviewer):
        join_request = type(self).objects.select_for_update().get(pk=self.pk)
        if join_request.status == self.Status.REJECTED:
            return
        if join_request.status != self.Status.PENDING:
            raise ValidationError('Somente solicitações pendentes podem ser rejeitadas.')

        join_request.status = self.Status.REJECTED
        join_request.reviewed_by = reviewer
        join_request.reviewed_at = timezone.now()
        join_request.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'],
        )
        self.status = join_request.status

class Role(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='roles')

    def __str__(self):
        return f"{self.name} ({self.team.name})"

class Unavailability(models.Model):
    description = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='unavailability')
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Unavailabilities'

    def __str__(self):
        return f'{self.description} ({self.user.first_name})'


class Schedule(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    hour = models.TimeField()
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f'{self.name} - {self.team.name} ({self.date})'

class ScheduleParticipation(models.Model):
    schedule = models.ForeignKey('Schedule', on_delete=models.CASCADE, related_name='participations')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='schedules')
    confirmation = models.BooleanField(default=False, null=True)
    roles = models.ManyToManyField('Role', related_name='participations_roles')
    
    class Meta:
        unique_together = ('schedule', 'user')
        verbose_name_plural = 'Participations'

    def __str__(self):
        return f'{self.schedule.name} - {self.user.first_name}'


class ScheduleConfirmationReminder(models.Model):
    WINDOW_CHOICES = (
        (72, "72 hours"),
        (48, "48 hours"),
        (24, "24 hours"),
    )

    participation = models.ForeignKey(
        ScheduleParticipation,
        on_delete=models.CASCADE,
        related_name="confirmation_reminders",
    )
    window_hours = models.PositiveSmallIntegerField(choices=WINDOW_CHOICES)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("participation", "window_hours"),
                name="unique_confirmation_reminder_window",
            ),
        ]

    def __str__(self):
        return f"{self.participation} - {self.window_hours}h"


class MonthlyUnavailabilityReminder(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="monthly_unavailability_reminders",
    )
    month = models.DateField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "month"),
                name="unique_monthly_unavailability_reminder",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.month:%Y-%m}"

class TeamInvitation(models.Model):
    recipient_email = models.EmailField(max_length=100)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='invitations')
    sender_name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.sender_name} convida {self.recipient_email} para equipe {self.team}'
    
class OrganizationInvitation(models.Model):
    recipient_email = models.EmailField(max_length=100)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='invitations')
    sender_name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.sender_name} convida {self.recipient_email} para organização {self.organization}'

class Request(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='requests')
    code = models.CharField(max_length=6)

    class Meta:
        verbose_name_plural = 'Requests'
    def __str__(self):
        return f'{self.user} solicita ingressar via codigo {self.code}'
