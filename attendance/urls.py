from django.urls import path
from . import views

urlpatterns = [
    # ── Main scanner page ──────────────────────────────────────────
    path('scanner/',                views.office_scanner,          name='office_scanner'),

    # ── QR Scan API ────────────────────────────────────────────────
    path('scan/',                   views.scan_qr_api,             name='scan_qr_api'),

    # ── Face Recognition APIs ──────────────────────────────────────
    path('face-scan/',              views.face_scan_api,           name='face_scan_api'),
    path('enroll-face/<int:pk>/',   views.enroll_face,             name='enroll_face'),

    # ── Fingerprint / WebAuthn APIs ────────────────────────────────
    path('fp/auth-options/',        views.webauthn_auth_options,   name='webauthn_auth_options'),
    path('fp/scan/',                views.fingerprint_scan_api,    name='fingerprint_scan_api'),
    path('fp/register/<int:pk>/',   views.webauthn_register_options, name='webauthn_register_options'),
    path('fp/register/<int:pk>/verify/', views.webauthn_register_verify, name='webauthn_register_verify'),

    # ── Geofence check ─────────────────────────────────────────────
    path('geofence-check/',         views.geofence_check_api,      name='geofence_check_api'),

    # ── Attendance log / history ───────────────────────────────────
    path('log/',                    views.attendance_log,          name='attendance_log'),
    path('employee/<int:pk>/history/', views.employee_attendance_history, name='employee_history'),
    path('manual/',                 views.manual_attendance,        name='manual_attendance'),
    path('api/live-status/',        views.live_status_api,         name='live_status_api'),
]
