import os
import uuid
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'docx', 'doc'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOC_EXTENSIONS
MAX_IMAGE_SIZE = 2 * 1024 * 1024   # 2 MB
MAX_DOC_SIZE = 10 * 1024 * 1024    # 10 MB


def allowed_file(filename, allowed=None):
    """Check if filename has an allowed extension."""
    if allowed is None:
        allowed = ALLOWED_EXTENSIONS
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed


def save_upload(file, folder="general", allowed=None, max_size=None):
    """
    Save an uploaded file to ``uploads/<folder>/`` with a unique UUID name.

    Parameters
    ----------
    file : FileStorage
        The uploaded file object from Flask ``request.files``.
    folder : str
        Sub-directory inside ``uploads/`` (e.g. "photos", "devices").
    allowed : set | None
        Allowed extensions.  Defaults to all known extensions.
    max_size : int | None
        Maximum file size in bytes.  Defaults to 2 MB for images, 10 MB for docs.

    Returns
    -------
    str
        Relative URL path suitable for database storage,
        e.g. ``/uploads/photos/<uuid>.jpg``.
    """
    if allowed is None:
        allowed = ALLOWED_EXTENSIONS

    if not file or not allowed_file(file.filename, allowed):
        ext_list = ', '.join(sorted(allowed)).upper()
        raise ValueError(f"Invalid file type. Allowed: {ext_list}")

    # Determine max size by file type when not explicitly provided
    extension = file.filename.rsplit('.', 1)[1].lower()
    if max_size is None:
        max_size = MAX_DOC_SIZE if extension in ALLOWED_DOC_EXTENSIONS else MAX_IMAGE_SIZE

    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > max_size:
        limit_mb = max_size / (1024 * 1024)
        raise ValueError(f"File too large. Max limit is {limit_mb:.0f} MB")

    # Build safe, unique filename
    safe_name = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}.{extension}"

    upload_path = os.path.join("uploads", folder)
    os.makedirs(upload_path, exist_ok=True)

    full_path = os.path.join(upload_path, unique_filename)
    file.save(full_path)

    # Return path that matches the /uploads/<path> serving route
    return f"/uploads/{folder}/{unique_filename}"
