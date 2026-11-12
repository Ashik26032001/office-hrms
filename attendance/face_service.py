"""
Face Recognition service using DeepFace.

Flow:
1. HR enrolls employee — uploads a clear face photo.
   We set face_enrolled=True on the Employee model.

2. At scanner — browser captures a webcam frame (base64 JPEG),
   sends it to /attendance/face-scan/ endpoint.

3. This service compares the captured frame against ALL enrolled
   employee face photos and returns the best match.

4. If confidence is above threshold → attendance is recorded.
"""
import os
import base64
import tempfile
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def decode_base64_image(b64_string):
    """
    Decodes a base64 image string (from browser canvas.toDataURL())
    to a temporary file. Returns the temp file path.
    b64_string may start with 'data:image/jpeg;base64,...'
    """
    if ',' in b64_string:
        b64_string = b64_string.split(',', 1)[1]

    image_data = base64.b64decode(b64_string)
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp.write(image_data)
    tmp.flush()
    tmp.close()
    return tmp.name


def verify_face(captured_b64, employee_photo_path):
    """
    Compare a captured image (base64) with a stored employee photo.

    Returns:
        dict: {
            'match':      bool,
            'distance':   float,
            'threshold':  float,
            'model':      str,
        }
    """
    try:
        from deepface import DeepFace

        captured_path = decode_base64_image(captured_b64)
        model     = getattr(settings, 'FACE_RECOGNITION_MODEL',    'VGG-Face')
        metric    = getattr(settings, 'FACE_RECOGNITION_DISTANCE', 'cosine')
        threshold = getattr(settings, 'FACE_RECOGNITION_THRESHOLD', 0.40)

        result = DeepFace.verify(
            img1_path  = captured_path,
            img2_path  = employee_photo_path,
            model_name = model,
            distance_metric = metric,
            enforce_detection = False,  # don't crash if face not perfectly detected
        )

        os.unlink(captured_path)  # clean up temp file

        return {
            'match':     result['verified'],
            'distance':  round(result['distance'], 4),
            'threshold': result['threshold'],
            'model':     model,
        }

    except Exception as e:
        logger.error(f"Face verification error: {e}")
        try:
            os.unlink(captured_path)
        except Exception:
            pass
        return {
            'match':     False,
            'distance':  None,
            'threshold': None,
            'model':     'error',
            'error':     str(e),
        }


def find_matching_employee(captured_b64):
    """
    Compare a captured face against ALL enrolled employees.
    Returns the best-matching Employee or None.

    Used when employee identity is unknown (face-only scan).
    """
    from employees.models import Employee

    enrolled = Employee.objects.filter(
        status='active',
        face_enrolled=True,
        face_photo__isnull=False,
    ).exclude(face_photo='')

    if not enrolled.exists():
        return None, {'error': 'No employees have face recognition enrolled.'}

    best_match    = None
    best_distance = float('inf')
    threshold     = getattr(settings, 'FACE_RECOGNITION_THRESHOLD', 0.40)

    for emp in enrolled:
        photo_path = emp.face_photo.path
        if not os.path.exists(photo_path):
            continue

        result = verify_face(captured_b64, photo_path)
        if result.get('error'):
            continue

        if result['match'] and result['distance'] < best_distance:
            best_distance = result['distance']
            best_match    = emp

    if best_match:
        return best_match, {
            'distance':  best_distance,
            'threshold': threshold,
            'model':     getattr(settings, 'FACE_RECOGNITION_MODEL', 'VGG-Face'),
        }

    return None, {
        'error': 'No matching face found. Please try again or use QR code.',
        'threshold': threshold,
    }
