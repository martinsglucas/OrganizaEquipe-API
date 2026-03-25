import uuid
from django.db import models
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

class Team(models.Model):
    name = models.CharField(max_length=100)
    admins = models.ManyToManyField('User', related_name='administered_teams')
    code_access = models.CharField(max_length=6, default=generate_unique_access_code, unique=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='teams')
    members = models.ManyToManyField('User', related_name='teams')

    def __str__(self):
        return self.name

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
