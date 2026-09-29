from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import (
    Organization,
    OrganizationInvitation,
    InvitationLink,
    PushSubscription,
    Request,
    Role,
    Schedule,
    ScheduleParticipation,
    Team,
    TeamInvitation,
    Unavailability,
    User,
)
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
admin.site.register(Organization)
admin.site.register(Request)


@admin.register(InvitationLink)
class InvitationLinkAdmin(admin.ModelAdmin):
    list_display = ('target_type', 'target', 'status', 'expires_at', 'updated_at')
    readonly_fields = ('token', 'created_by', 'created_at', 'updated_at')
    search_fields = ('organization__name', 'team__name', 'token')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'device_label',
        'platform',
        'browser',
        'permission',
        'is_active',
        'last_seen_at',
    )
    list_filter = (
        'platform',
        'browser',
        'permission',
        'is_active',
        'is_ios',
        'is_standalone',
    )
    search_fields = (
        'user__email',
        'user__first_name',
        'user__last_name',
        'device_label',
        'token',
    )
    readonly_fields = (
        'user',
        'token',
        'platform',
        'browser',
        'device_label',
        'is_ios',
        'is_standalone',
        'permission',
        'is_active',
        'last_seen_at',
        'created_at',
        'updated_at',
    )
    list_select_related = ('user',)
    ordering = ('-last_seen_at',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class RoleInline(admin.TabularInline):
    model = Role
    extra = 1

class ScheduleParticipationInline(admin.TabularInline):
    model = ScheduleParticipation
    extra = 1

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = (RoleInline,)
    list_display = ('name', 'organization', 'visibility', 'code_access')
    list_filter = ('organization', 'visibility')
    search_fields = ('name', 'code_access')
    list_select_related = ('organization',)
    ordering = ('name', 'pk')

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    inlines = (ScheduleParticipationInline,)
    list_display = ('name', 'team', 'date', 'hour')
    list_filter = ('team', 'date')
    search_fields = ('name', 'team__name')
    list_select_related = ('team',)
    ordering = ('-date', '-hour', 'name', 'pk')


@admin.register(ScheduleParticipation)
class ScheduleParticipationAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'user', 'confirmation')
    list_filter = ('confirmation', 'schedule__team')
    search_fields = (
        'schedule__name',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    list_select_related = ('schedule', 'schedule__team', 'user')
    ordering = ('confirmation', 'pk')


@admin.register(Unavailability)
class UnavailabilityAdmin(admin.ModelAdmin):
    list_display = ('description', 'user', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = (
        'description',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    list_select_related = ('user',)
    ordering = ('-start_date', '-end_date', 'pk')


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'sender_name', 'team')
    list_filter = ('team',)
    search_fields = ('recipient_email', 'sender_name', 'team__name')
    list_select_related = ('team',)
    ordering = ('recipient_email', 'pk')


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'sender_name', 'organization')
    list_filter = ('organization',)
    search_fields = (
        'recipient_email',
        'sender_name',
        'organization__name',
    )
    list_select_related = ('organization',)
    ordering = ('recipient_email', 'pk')
