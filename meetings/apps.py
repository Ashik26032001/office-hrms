from django.apps import AppConfig


class MeetingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meetings'
    verbose_name = 'Meeting Scheduler'

    def ready(self):
        """Start the background notification engine when Django loads."""
        import os
        # Only start in the main process (not the auto-reloader child)
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('DJANGO_SETTINGS_MODULE'):
            # Production / gunicorn path
            from .notification_engine import start_background_notifier
            start_background_notifier()
        elif os.environ.get('RUN_MAIN') == 'true':
            # runserver main process
            from .notification_engine import start_background_notifier
            start_background_notifier()
