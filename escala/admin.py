from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, Role, Team, Unavailability, Schedule, ScheduleParticipation, Organization, TeamInvitation, OrganizationInvitation, Request
from django.contrib.auth.models import Group, Permission


class UserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')

class UserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')

class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

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

admin.site.register(User, UserAdmin)
admin.site.register(Role)
admin.site.register(Unavailability)
admin.site.register(ScheduleParticipation)
admin.site.register(Organization)
admin.site.register(TeamInvitation)
admin.site.register(OrganizationInvitation)
admin.site.register(Request)

class RoleInline(admin.TabularInline):
    model = Role
    extra = 1

class ScheduleParticipationInline(admin.TabularInline):
    model = ScheduleParticipation
    extra = 1

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = (RoleInline,)
    list_display = ('name', 'code_access')
    search_fields = ('name', 'code_access')

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    inlines = (ScheduleParticipationInline,)