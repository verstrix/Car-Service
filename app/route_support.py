import os
from datetime import datetime
from functools import wraps
from importlib import import_module
from uuid import uuid4

from flask import current_app, flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from .models import Car, User, WorkOrder


ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_WORK_ORDER_STATUSES = {'open', 'in_progress', 'awaiting_parts', 'completed'}
MIN_YEAR = 1950
STATUS_META = {
    'open': {'label': 'Приета', 'badge': 'text-bg-secondary'},
    'in_progress': {'label': 'В ремонт', 'badge': 'text-bg-primary'},
    'awaiting_parts': {'label': 'Чака части', 'badge': 'text-bg-warning'},
    'completed': {'label': 'Приключена', 'badge': 'text-bg-success'},
}
ROLE_META = {
    'manager': 'Мениджър',
    'mechanic': 'Механик',
    'client': 'Клиент',
}


def register_template_helpers(app):
    @app.context_processor
    def inject_status_helpers():
        return {
            'status_label': status_label,
            'status_badge': status_badge,
            'status_meta': STATUS_META,
            'role_label': role_label,
            'pdf_export_enabled': pdf_export_available(),
        }


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def current_max_year() -> int:
    return datetime.now().year + 1


def parse_year(year_raw: str):
    year_raw = (year_raw or '').strip()
    if not year_raw:
        return None, None
    if not year_raw.isdigit():
        return None, f'Годината трябва да е число между {MIN_YEAR} и {current_max_year()}.'
    year = int(year_raw)
    if year < MIN_YEAR or year > current_max_year():
        return None, f'Годината трябва да е между {MIN_YEAR} и {current_max_year()}.'
    return year, None


def normalize_phone(phone: str) -> str:
    return (phone or '').strip()


def resolve_optional_int(raw_value, field_label: str):
    raw_value = (raw_value or '').strip()
    if not raw_value:
        return None, None
    if not raw_value.isdigit():
        return None, f'Невалидна стойност за {field_label}.'
    return int(raw_value), None


def client_phone(user: User | None) -> str | None:
    normalized = normalize_phone(getattr(user, 'phone', ''))
    return normalized or None


def client_car_filter(user: User):
    clauses = [Car.user_id == user.id]
    phone = client_phone(user)
    if phone:
        clauses.append(Car.owner_phone == phone)
    return or_(*clauses)


def client_order_filter(user: User):
    clauses = [WorkOrder.client_id == user.id, Car.user_id == user.id]
    phone = client_phone(user)
    if phone:
        clauses.append(Car.owner_phone == phone)
    return or_(*clauses)


def linked_client_id_for_car(car: Car):
    if car.user_id:
        return car.user_id
    if not car.owner_phone:
        return None
    matching_clients = User.query.filter_by(role='client', phone=car.owner_phone).all()
    if len(matching_clients) == 1:
        return matching_clients[0].id
    return None


def resolve_mechanic(mechanic_id):
    if mechanic_id is None:
        return None, None
    mechanic = User.query.filter_by(id=mechanic_id, role='mechanic').first()
    if mechanic is None:
        return None, 'Избраният механик не съществува.'
    return mechanic, None


def save_image(file_storage, category: str = 'misc'):
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_file(file_storage.filename):
        return None, 'Невалиден формат на снимката. Разрешени са: png, jpg, jpeg, gif, webp.'

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None, 'Невалидно име на файл.'

    ext = filename.rsplit('.', 1)[1].lower()
    generated = f'uploads/{category}/{uuid4().hex}.{ext}'
    absolute_path = os.path.join(current_app.root_path, 'static', *generated.split('/'))
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    file_storage.save(absolute_path)
    return generated, None


def remove_image(relative_path: str | None):
    if not relative_path:
        return
    try:
        absolute_path = os.path.join(current_app.root_path, 'static', *relative_path.split('/'))
        if os.path.isfile(absolute_path):
            os.remove(absolute_path)
    except OSError:
        pass


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash('Нямате достъп до тази страница.', 'danger')
                return redirect(url_for('dashboard'))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def status_label(status: str) -> str:
    return STATUS_META.get(status, {}).get('label', status)


def status_badge(status: str) -> str:
    return STATUS_META.get(status, {}).get('badge', 'text-bg-light')


def role_label(role: str) -> str:
    return ROLE_META.get(role, role)


def load_pdf_dependencies():
    pagesizes = import_module('reportlab.lib.pagesizes')
    utils = import_module('reportlab.lib.utils')
    pdfbase = import_module('reportlab.pdfbase')
    ttfonts = import_module('reportlab.pdfbase.ttfonts')
    pdfgen = import_module('reportlab.pdfgen.canvas')
    return {
        'A4': pagesizes.A4,
        'simple_split': utils.simpleSplit,
        'pdfmetrics': pdfbase.pdfmetrics,
        'ttfont': ttfonts.TTFont,
        'canvas': pdfgen,
    }


def pdf_export_available() -> bool:
    try:
        load_pdf_dependencies()
    except ImportError:
        return False
    return True


def car_access_allowed(car: Car) -> bool:
    if current_user.role in {'manager', 'mechanic'}:
        return True
    if car.user_id == current_user.id:
        return True
    phone = client_phone(current_user)
    return bool(phone and car.owner_phone == phone)


def order_access_allowed(order: WorkOrder) -> bool:
    if current_user.role == 'manager':
        return True
    if current_user.role == 'mechanic':
        return order.mechanic_id in (None, current_user.id)
    return order.client_id == current_user.id or car_access_allowed(order.car)


def order_edit_allowed(order: WorkOrder) -> bool:
    if current_user.role == 'manager':
        return True
    if current_user.role == 'mechanic':
        return order.mechanic_id in (None, current_user.id)
    return False
