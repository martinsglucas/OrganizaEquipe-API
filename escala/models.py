import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UsuarioManager(BaseUserManager):
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

class Usuario(AbstractBaseUser, PermissionsMixin):
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

    objects = UsuarioManager()

    def __str__(self):
        return self.first_name

class Organizacao(models.Model):
    nome = models.CharField(max_length=100)
    administradores = models.ManyToManyField('Usuario', related_name='organizacoes_administradas')
    membros = models.ManyToManyField('Usuario', related_name='organizacoes')
    class Meta:
        verbose_name_plural = 'Organizacoes'

    def __str__(self):
        return self.nome

def generate_unique_access_code():
    while True:
        code = uuid.uuid4().hex[:6].upper()
        if not Equipe.objects.filter(codigo_de_acesso=code).exists():
            return code

class Equipe(models.Model):
    nome = models.CharField(max_length=100)
    administradores = models.ManyToManyField('Usuario', related_name='equipes_administradas')
    codigo_de_acesso = models.CharField(max_length=6, default=generate_unique_access_code, unique=True)
    organizacao = models.ForeignKey('Organizacao', on_delete=models.CASCADE, related_name='equipes')
    membros = models.ManyToManyField('Usuario', related_name='equipes')

    def __str__(self):
        return self.nome

class Funcao(models.Model):
    nome = models.CharField(max_length=100)
    equipe = models.ForeignKey('Equipe', on_delete=models.CASCADE, related_name='funcoes')
    class Meta:
        verbose_name_plural = 'Funcoes'

    def __str__(self):
        return f"{self.nome} ({self.equipe.nome})"

class Indisponibilidade(models.Model):
    descricao = models.CharField(max_length=100)
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='indisponibilidades')
    data_inicio = models.DateField()
    data_fim = models.DateField(blank=True, null=True)

    def __str__(self):
        return f'{self.descricao} ({self.usuario.first_name})'


class Escala(models.Model):
    nome = models.CharField(max_length=100)
    equipe = models.ForeignKey('Equipe', on_delete=models.CASCADE, related_name='escalas')
    data = models.DateField()
    hora = models.TimeField()

    def __str__(self):
        return f'{self.nome} - {self.equipe.nome} ({self.data})'

class ParticipacaoEscala(models.Model):
    escala = models.ForeignKey('Escala', on_delete=models.CASCADE, related_name='participacoes')
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='escalas')
    confirmacao = models.BooleanField(default=False, null=True)
    funcoes = models.ManyToManyField('Funcao', related_name='participacoes_funcoes')
    
    class Meta:
        unique_together = ('escala', 'usuario')
        verbose_name_plural = 'Participacoes'

    def __str__(self):
        return f'{self.escala.nome} - {self.usuario.first_name}'

class Convite(models.Model):
    email_destinatario = models.EmailField(max_length=100)
    equipe = models.ForeignKey('Equipe', on_delete=models.CASCADE, related_name='convites')
    nome_remetente = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.nome_remetente} convida {self.email_destinatario} para equipe {self.equipe}'

class Solicitacao(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='solicitacoes')
    codigo_equipe = models.CharField(max_length=6)

    class Meta:
        verbose_name_plural = 'Solicitacoes'
    def __str__(self):
        return f'{self.usuario} solicita ingressar via codigo {self.codigo_equipe}'
