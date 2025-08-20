from django.apps import AppConfig

class EscalaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'escala'
    def ready(self):
        import escala.signals
        from django.db.models.signals import post_migrate
        from django.contrib.auth.models import Group, Permission

        CODENAMES=[
            'add_organization', 'change_organization', 'delete_organization', 'view_organization', 
            'add_team', 'change_team', 'delete_team', 'view_team', 
            'add_role', 'change_role', 'delete_role', 'view_role', 
            'add_unavailability', 'change_unavailability', 'delete_unavailability', 'view_unavailability', 
            'add_schedule', 'change_schedule', 'delete_schedule', 'view_schedule', 
            'add_scheduleparticipation', 'change_scheduleparticipation', 'delete_scheduleparticipation', 'view_scheduleparticipation',
            'add_teaminvitation', 'change_teaminvitation', 'delete_teaminvitation', 'view_teaminvitation',
            'add_organizationinvitation', 'change_organizationinvitation', 'delete_organizationinvitation', 'view_organizationinvitation',
            'add_request', 'change_request', 'delete_request', 'view_request',
            'add_user', 'change_user', 'delete_user', 'view_user'
        ]

        def create_default_groups(sender, **kwargs):
            group, _ = Group.objects.get_or_create(name="Users")
            perms = list(Permission.objects.filter(codename__in=CODENAMES))
            group.permissions.set(perms)
        
        post_migrate.connect(create_default_groups, dispatch_uid="escala.create_default_groups")