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
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.first_name

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
        return f'{self.escala.nome} - {self.usuario.first_name}'

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
