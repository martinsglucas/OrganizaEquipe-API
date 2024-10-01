from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario, Funcao, Equipe, Indisponibilidade, Escala, ParticipacaoEscala

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