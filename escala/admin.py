from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario, Funcao, Equipe, Indisponibilidade, Escala, ParticipacaoEscala, Organizacao, Convite, Solicitacao
from django.contrib.auth.models import Group, Permission

group, created = Group.objects.get_or_create(name='Usuarios')
permissions = Permission.objects.filter(codename__in=[
    'add_organizacao', 'change_organizacao', 'delete_organizacao', 'view_organizacao', 
    'add_equipe', 'change_equipe', 'delete_equipe', 'view_equipe', 
    'add_funcao', 'change_funcao', 'delete_funcao', 'view_funcao', 
    'add_indisponibilidade', 'change_indisponibilidade', 'delete_indisponibilidade', 'view_indisponibilidade', 
    'add_escala', 'change_escala', 'delete_escala', 'view_escala', 
    'add_participacaoescala', 'change_participacaoescala', 'delete_participacaoescala', 'view_participacaoescala',
    'add_convite', 'change_convite', 'delete_convite', 'view_convite'
    'add_solicitacao', 'change_solicitacao', 'delete_solicitacao', 'view_solicitacao'
    'add_usuario', 'change_usuario', 'delete_usuario', 'view_usuario'])
group.permissions.set(permissions)

class UsuarioCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')

class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')

class UsuarioAdmin(BaseUserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm

    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'username')}),
        ('Permissões', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ['last_login']}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}
        ),
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions')

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Funcao)
admin.site.register(Indisponibilidade)
admin.site.register(ParticipacaoEscala)
admin.site.register(Organizacao)
admin.site.register(Convite)
admin.site.register(Solicitacao)

class FuncaoInline(admin.TabularInline):
    model = Funcao
    extra = 1

class ParticipacaoEscalaInline(admin.TabularInline):
    model = ParticipacaoEscala
    extra = 1

@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    inlines = (FuncaoInline,)
    list_display = ('nome', 'codigo_de_acesso')
    search_fields = ('nome', 'codigo_de_acesso')

@admin.register(Escala)
class EscalaAdmin(admin.ModelAdmin):
    inlines = (ParticipacaoEscalaInline,)