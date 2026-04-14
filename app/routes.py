import os
from datetime import datetime
from functools import wraps
from io import BytesIO
from uuid import uuid4

from flask import render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_user, logout_user, login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from . import db
from .models import User, Car, Part, WorkOrder, WorkOrderPart


ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_WORK_ORDER_STATUSES = {'open', 'in_progress', 'awaiting_parts', 'completed'}
MIN_YEAR = 1950
STATUS_META = {
    'open': {'label': 'Приета', 'badge': 'text-bg-secondary'},
    'in_progress': {'label': 'В ремонт', 'badge': 'text-bg-primary'},
    'awaiting_parts': {'label': 'Чака части', 'badge': 'text-bg-warning'},
    'completed': {'label': 'Приключена', 'badge': 'text-bg-success'},
}


def register_routes(app):
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

    def current_max_year() -> int:
        return datetime.utcnow().year + 1

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

    def car_access_allowed(car: Car) -> bool:
        if current_user.role in {'manager', 'mechanic'}:
            return True
        return car.user_id == current_user.id or car.owner_phone == current_user.phone

    def order_access_allowed(order: WorkOrder) -> bool:
        if current_user.role == 'manager':
            return True
        if current_user.role == 'mechanic':
            return order.mechanic_id in (None, current_user.id)
        return order.client_id == current_user.id

    def order_edit_allowed(order: WorkOrder) -> bool:
        if current_user.role == 'manager':
            return True
        if current_user.role == 'mechanic':
            return order.mechanic_id in (None, current_user.id)
        return False

    @app.context_processor
    def inject_status_helpers():
        return {
            'status_label': status_label,
            'status_badge': status_badge,
            'status_meta': STATUS_META,
        }

    @app.route('/')
    def landing():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('landing.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Успешен вход.', 'success')
                return redirect(url_for('dashboard'))
            flash('Невалидно потребителско име или парола.', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Успешно излязохте от системата.', 'info')
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        stats = {
            'cars': Car.query.count(),
            'parts': Part.query.count(),
            'orders': WorkOrder.query.count(),
            'users': User.query.count(),
            'low_stock': Part.query.filter(Part.quantity <= Part.min_quantity).count(),
            'open_orders': WorkOrder.query.filter_by(status='open').count(),
            'in_progress_orders': WorkOrder.query.filter_by(status='in_progress').count(),
            'awaiting_parts_orders': WorkOrder.query.filter_by(status='awaiting_parts').count(),
            'completed_orders': WorkOrder.query.filter_by(status='completed').count(),
        }
        recent_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(5).all()
        if current_user.role == 'manager':
            return render_template('dashboard_manager.html', stats=stats, recent_orders=recent_orders)
        if current_user.role == 'mechanic':
            assigned = WorkOrder.query.filter_by(mechanic_id=current_user.id).order_by(WorkOrder.updated_at.desc()).all()
            return render_template('dashboard_mechanic.html', stats=stats, assigned_orders=assigned)
        client_cars = Car.query.filter((Car.user_id == current_user.id) | (Car.owner_phone == current_user.phone)).all()
        client_orders = WorkOrder.query.filter_by(client_id=current_user.id).order_by(WorkOrder.created_at.desc()).all()
        return render_template('dashboard_client.html', stats=stats, client_cars=client_cars, client_orders=client_orders)

    @app.route('/cars', methods=['GET', 'POST'])
    @login_required
    def list_cars():
        if request.method == 'POST':
            if current_user.role != 'manager':
                flash('Само мениджър може да добавя автомобили.', 'danger')
                return redirect(url_for('list_cars'))

            vin = request.form.get('vin', '').strip().upper()
            make = request.form.get('make', '').strip()
            model = request.form.get('model', '').strip()
            owner_name = request.form.get('owner_name', '').strip()
            registration_number = request.form.get('registration_number', '').strip().upper()
            owner_phone = normalize_phone(request.form.get('owner_phone', ''))
            client_user_id = request.form.get('user_id') or None
            year, year_error = parse_year(request.form.get('year', ''))

            if not vin or not make or not model or not owner_name:
                flash('VIN, марка, модел и собственик са задължителни.', 'danger')
                return redirect(url_for('list_cars'))
            if len(vin) < 8:
                flash('VIN номерът е прекалено кратък.', 'danger')
                return redirect(url_for('list_cars'))
            if year_error:
                flash(year_error, 'danger')
                return redirect(url_for('list_cars'))
            if Car.query.filter_by(vin=vin).first():
                flash('Вече има автомобил с този VIN.', 'danger')
                return redirect(url_for('list_cars'))
            if registration_number and Car.query.filter_by(registration_number=registration_number).first():
                flash('Вече има автомобил с този регистрационен номер.', 'danger')
                return redirect(url_for('list_cars'))

            image_filename, image_error = save_image(request.files.get('image'), 'cars')
            if image_error:
                flash(image_error, 'danger')
                return redirect(url_for('list_cars'))

            car = Car(
                vin=vin,
                make=make,
                model=model,
                owner_name=owner_name,
                owner_phone=owner_phone,
                registration_number=registration_number or None,
                year=year,
                image_filename=image_filename,
                user_id=int(client_user_id) if client_user_id else None,
            )
            db.session.add(car)
            db.session.commit()
            flash('Автомобилът е добавен успешно.', 'success')
            return redirect(url_for('list_cars'))

        search = request.args.get('q', '').strip()
        query = Car.query.order_by(Car.created_at.desc())
        if current_user.role == 'client':
            query = query.filter((Car.user_id == current_user.id) | (Car.owner_phone == current_user.phone))
        if search:
            like = f'%{search}%'
            query = query.filter(
                or_(
                    Car.vin.ilike(like),
                    Car.registration_number.ilike(like),
                    Car.make.ilike(like),
                    Car.model.ilike(like),
                    Car.owner_name.ilike(like),
                    Car.owner_phone.ilike(like),
                )
            )
        cars = query.all()
        clients = User.query.filter_by(role='client').order_by(User.username.asc()).all() if current_user.role == 'manager' else []
        return render_template('cars.html', cars=cars, clients=clients, search=search)

    @app.route('/cars/<int:car_id>')
    @login_required
    def car_details(car_id):
        car = Car.query.get_or_404(car_id)
        if not car_access_allowed(car):
            flash('Нямате достъп до този автомобил.', 'danger')
            return redirect(url_for('list_cars'))
        return render_template('car_details.html', car=car, orders=car.orders)

    @app.route('/cars/<int:car_id>/edit', methods=['GET', 'POST'])
    @role_required('manager')
    def edit_car(car_id):
        car = Car.query.get_or_404(car_id)
        clients = User.query.filter_by(role='client').order_by(User.username.asc()).all()
        if request.method == 'POST':
            vin = request.form.get('vin', '').strip().upper()
            make = request.form.get('make', '').strip()
            model = request.form.get('model', '').strip()
            owner_name = request.form.get('owner_name', '').strip()
            registration_number = request.form.get('registration_number', '').strip().upper()
            owner_phone = normalize_phone(request.form.get('owner_phone', ''))
            client_user_id = request.form.get('user_id') or None
            year, year_error = parse_year(request.form.get('year', ''))

            if not vin or not make or not model or not owner_name:
                flash('VIN, марка, модел и собственик са задължителни.', 'danger')
                return redirect(url_for('edit_car', car_id=car.id))
            if len(vin) < 8:
                flash('VIN номерът е прекалено кратък.', 'danger')
                return redirect(url_for('edit_car', car_id=car.id))
            if year_error:
                flash(year_error, 'danger')
                return redirect(url_for('edit_car', car_id=car.id))
            if Car.query.filter(Car.vin == vin, Car.id != car.id).first():
                flash('Вече има автомобил с този VIN.', 'danger')
                return redirect(url_for('edit_car', car_id=car.id))
            if registration_number and Car.query.filter(Car.registration_number == registration_number, Car.id != car.id).first():
                flash('Вече има автомобил с този регистрационен номер.', 'danger')
                return redirect(url_for('edit_car', car_id=car.id))

            new_image = request.files.get('image')
            if new_image and new_image.filename:
                image_filename, image_error = save_image(new_image, 'cars')
                if image_error:
                    flash(image_error, 'danger')
                    return redirect(url_for('edit_car', car_id=car.id))
                remove_image(car.image_filename)
                car.image_filename = image_filename
            if request.form.get('remove_image') == '1':
                remove_image(car.image_filename)
                car.image_filename = None

            car.vin = vin
            car.make = make
            car.model = model
            car.owner_name = owner_name
            car.owner_phone = owner_phone
            car.registration_number = registration_number or None
            car.year = year
            car.user_id = int(client_user_id) if client_user_id else None
            db.session.commit()
            flash('Автомобилът е обновен успешно.', 'success')
            return redirect(url_for('car_details', car_id=car.id))
        return render_template('edit_car.html', car=car, clients=clients)

    @app.route('/cars/<int:car_id>/delete', methods=['POST'])
    @role_required('manager')
    def delete_car(car_id):
        car = Car.query.get_or_404(car_id)
        remove_image(car.image_filename)
        db.session.delete(car)
        db.session.commit()
        flash('Автомобилът е изтрит.', 'info')
        return redirect(url_for('list_cars'))

    @app.route('/parts', methods=['GET', 'POST'])
    @login_required
    def list_parts():
        if request.method == 'POST':
            if current_user.role != 'manager':
                flash('Само мениджър може да добавя части.', 'danger')
                return redirect(url_for('list_parts'))
            part_number = request.form.get('part_number', '').strip().upper()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            quantity_raw = request.form.get('quantity', '0').strip()
            unit_price_raw = request.form.get('unit_price', '0').strip()
            min_quantity_raw = request.form.get('min_quantity', '5').strip()
            if not part_number or not name:
                flash('Номерът и името на частта са задължителни.', 'danger')
                return redirect(url_for('list_parts'))
            if Part.query.filter_by(part_number=part_number).first():
                flash('Вече има част с този номер.', 'danger')
                return redirect(url_for('list_parts'))
            try:
                quantity = int(quantity_raw)
                min_quantity = int(min_quantity_raw)
                unit_price = float(unit_price_raw)
                if quantity < 0 or min_quantity < 0 or unit_price < 0:
                    raise ValueError
            except ValueError:
                flash('Количеството, минимумът и цената трябва да са неотрицателни числа.', 'danger')
                return redirect(url_for('list_parts'))
            image_filename, image_error = save_image(request.files.get('image'), 'parts')
            if image_error:
                flash(image_error, 'danger')
                return redirect(url_for('list_parts'))

            part = Part(
                part_number=part_number,
                name=name,
                description=description,
                quantity=quantity,
                min_quantity=min_quantity,
                unit_price=unit_price,
                image_filename=image_filename,
            )
            db.session.add(part)
            db.session.commit()
            flash('Частта е добавена успешно.', 'success')
            return redirect(url_for('list_parts'))

        search = request.args.get('q', '').strip()
        query = Part.query.order_by(Part.created_at.desc())
        if search:
            like = f'%{search}%'
            query = query.filter(or_(Part.part_number.ilike(like), Part.name.ilike(like), Part.description.ilike(like)))
        parts = query.all()
        return render_template('parts.html', parts=parts, search=search)

    @app.route('/parts/<int:part_id>')
    @login_required
    def part_details(part_id):
        part = Part.query.get_or_404(part_id)
        return render_template('part_details.html', part=part)

    @app.route('/parts/<int:part_id>/edit', methods=['GET', 'POST'])
    @role_required('manager')
    def edit_part(part_id):
        part = Part.query.get_or_404(part_id)
        if request.method == 'POST':
            part_number = request.form.get('part_number', '').strip().upper()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            quantity_raw = request.form.get('quantity', '0').strip()
            unit_price_raw = request.form.get('unit_price', '0').strip()
            min_quantity_raw = request.form.get('min_quantity', '5').strip()
            if not part_number or not name:
                flash('Номерът и името на частта са задължителни.', 'danger')
                return redirect(url_for('edit_part', part_id=part.id))
            if Part.query.filter(Part.part_number == part_number, Part.id != part.id).first():
                flash('Вече има част с този номер.', 'danger')
                return redirect(url_for('edit_part', part_id=part.id))
            try:
                quantity = int(quantity_raw)
                min_quantity = int(min_quantity_raw)
                unit_price = float(unit_price_raw)
                if quantity < 0 or min_quantity < 0 or unit_price < 0:
                    raise ValueError
            except ValueError:
                flash('Количеството, минимумът и цената трябва да са неотрицателни числа.', 'danger')
                return redirect(url_for('edit_part', part_id=part.id))

            new_image = request.files.get('image')
            if new_image and new_image.filename:
                image_filename, image_error = save_image(new_image, 'parts')
                if image_error:
                    flash(image_error, 'danger')
                    return redirect(url_for('edit_part', part_id=part.id))
                remove_image(part.image_filename)
                part.image_filename = image_filename
            if request.form.get('remove_image') == '1':
                remove_image(part.image_filename)
                part.image_filename = None

            part.part_number = part_number
            part.name = name
            part.description = description
            part.quantity = quantity
            part.min_quantity = min_quantity
            part.unit_price = unit_price
            db.session.commit()
            flash('Частта е обновена успешно.', 'success')
            return redirect(url_for('part_details', part_id=part.id))
        return render_template('edit_part.html', part=part)

    @app.route('/parts/<int:part_id>/delete', methods=['POST'])
    @role_required('manager')
    def delete_part(part_id):
        part = Part.query.get_or_404(part_id)
        remove_image(part.image_filename)
        db.session.delete(part)
        db.session.commit()
        flash('Частта е изтрита.', 'info')
        return redirect(url_for('list_parts'))

    @app.route('/work-orders', methods=['GET', 'POST'])
    @login_required
    def list_work_orders():
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            car_id = request.form.get('car_id')
            mechanic_id = request.form.get('mechanic_id') or None
            labor_cost_raw = request.form.get('labor_cost', '0').strip()
            notes = request.form.get('notes', '').strip()
            if not title or not description or not car_id:
                flash('Заглавие, описание и автомобил са задължителни.', 'danger')
                return redirect(url_for('list_work_orders'))
            car = Car.query.get_or_404(int(car_id))
            if current_user.role == 'client' and not car_access_allowed(car):
                flash('Можете да създавате поръчки само за свои автомобили.', 'danger')
                return redirect(url_for('list_work_orders'))
            try:
                labor_cost = float(labor_cost_raw or 0)
                if labor_cost < 0:
                    raise ValueError
            except ValueError:
                flash('Невалидна цена за труд.', 'danger')
                return redirect(url_for('list_work_orders'))

            requested_status = request.form.get('status', 'open')
            status = requested_status if requested_status in ALLOWED_WORK_ORDER_STATUSES else 'open'
            order = WorkOrder(
                title=title,
                description=description,
                car_id=car.id,
                mechanic_id=int(mechanic_id) if mechanic_id else None,
                client_id=current_user.id if current_user.role == 'client' else car.user_id,
                created_by_id=current_user.id,
                labor_cost=labor_cost,
                notes=notes,
                status='open' if current_user.role == 'client' else status,
            )
            db.session.add(order)
            db.session.commit()
            flash('Работната поръчка е създадена успешно.', 'success')
            return redirect(url_for('list_work_orders'))

        selected_status = request.args.get('status', '').strip()
        search = request.args.get('q', '').strip()
        query = WorkOrder.query.join(Car).order_by(WorkOrder.created_at.desc())
        if current_user.role == 'mechanic':
            query = query.filter((WorkOrder.mechanic_id == current_user.id) | (WorkOrder.mechanic_id.is_(None)))
        elif current_user.role == 'client':
            query = query.filter(WorkOrder.client_id == current_user.id)
        if selected_status in ALLOWED_WORK_ORDER_STATUSES:
            query = query.filter(WorkOrder.status == selected_status)
        if search:
            like = f'%{search}%'
            query = query.filter(
                or_(
                    WorkOrder.title.ilike(like),
                    WorkOrder.description.ilike(like),
                    WorkOrder.notes.ilike(like),
                    Car.registration_number.ilike(like),
                    Car.vin.ilike(like),
                    Car.make.ilike(like),
                    Car.model.ilike(like),
                    Car.owner_name.ilike(like),
                )
            )
        work_orders = query.all()
        if current_user.role == 'client':
            cars = Car.query.filter((Car.user_id == current_user.id) | (Car.owner_phone == current_user.phone)).all()
        else:
            cars = Car.query.order_by(Car.make.asc(), Car.model.asc()).all()
        mechanics = User.query.filter_by(role='mechanic').all()
        parts = Part.query.order_by(Part.name.asc()).all()
        status_counts_query = WorkOrder.query
        if current_user.role == 'mechanic':
            status_counts_query = status_counts_query.filter((WorkOrder.mechanic_id == current_user.id) | (WorkOrder.mechanic_id.is_(None)))
        elif current_user.role == 'client':
            status_counts_query = status_counts_query.filter_by(client_id=current_user.id)
        status_counts = {code: status_counts_query.filter_by(status=code).count() for code in ALLOWED_WORK_ORDER_STATUSES}
        total_visible_orders = sum(status_counts.values())
        return render_template(
            'work_orders.html',
            work_orders=work_orders,
            cars=cars,
            mechanics=mechanics,
            parts=parts,
            selected_status=selected_status,
            search=search,
            status_counts=status_counts,
            total_visible_orders=total_visible_orders,
        )

    @app.route('/work-orders/<int:order_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_work_order(order_id):
        order = WorkOrder.query.get_or_404(order_id)
        if not order_edit_allowed(order):
            flash('Нямате право да редактирате тази поръчка.', 'danger')
            return redirect(url_for('list_work_orders'))
        cars = Car.query.order_by(Car.make.asc(), Car.model.asc()).all() if current_user.role == 'manager' else [order.car]
        mechanics = User.query.filter_by(role='mechanic').order_by(User.username.asc()).all()
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            notes = request.form.get('notes', '').strip()
            labor_cost_raw = request.form.get('labor_cost', '0').strip()
            requested_status = request.form.get('status', order.status)
            mechanic_id = request.form.get('mechanic_id') or None
            car_id = request.form.get('car_id') or str(order.car_id)

            if not title or not description:
                flash('Заглавие и описание са задължителни.', 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))
            try:
                labor_cost = float(labor_cost_raw or 0)
                if labor_cost < 0:
                    raise ValueError
            except ValueError:
                flash('Невалидна цена за труд.', 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))
            if requested_status not in ALLOWED_WORK_ORDER_STATUSES:
                flash('Невалиден статус.', 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))
            if current_user.role == 'manager':
                order.car_id = int(car_id)
                order.mechanic_id = int(mechanic_id) if mechanic_id else None
            elif current_user.role == 'mechanic' and order.mechanic_id in (None, current_user.id):
                order.mechanic_id = current_user.id if mechanic_id else order.mechanic_id
            order.title = title
            order.description = description
            order.notes = notes
            order.labor_cost = labor_cost
            order.status = requested_status
            db.session.commit()
            flash('Поръчката е обновена успешно.', 'success')
            return redirect(url_for('list_work_orders'))
        return render_template('edit_work_order.html', order=order, cars=cars, mechanics=mechanics)

    @app.route('/work-orders/<int:order_id>/status', methods=['POST'])
    @role_required('manager', 'mechanic')
    def update_work_order_status(order_id):
        order = WorkOrder.query.get_or_404(order_id)
        if not order_edit_allowed(order):
            flash('Нямате право да редактирате тази поръчка.', 'danger')
            return redirect(url_for('list_work_orders'))
        status = request.form.get('status', 'open')
        mechanic_id = request.form.get('mechanic_id') or None
        if status not in ALLOWED_WORK_ORDER_STATUSES:
            flash('Невалиден статус.', 'danger')
            return redirect(url_for('list_work_orders'))
        order.status = status
        if current_user.role == 'manager':
            order.mechanic_id = int(mechanic_id) if mechanic_id else None
        elif current_user.role == 'mechanic' and order.mechanic_id in (None, current_user.id):
            order.mechanic_id = current_user.id
        order.notes = request.form.get('notes', order.notes)
        db.session.commit()
        flash('Статусът е обновен.', 'success')
        return redirect(url_for('list_work_orders', status=request.args.get('status', ''), q=request.args.get('q', '')))

    @app.route('/work-orders/<int:order_id>/add-part', methods=['POST'])
    @role_required('manager', 'mechanic')
    def add_part_to_order(order_id):
        order = WorkOrder.query.get_or_404(order_id)
        if not order_edit_allowed(order):
            flash('Нямате право да добавяте части към тази поръчка.', 'danger')
            return redirect(url_for('list_work_orders'))
        part_id = request.form.get('part_id')
        quantity_raw = request.form.get('quantity_used', '1')
        if not part_id:
            flash('Изберете част.', 'danger')
            return redirect(url_for('list_work_orders'))
        try:
            quantity = int(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash('Количеството трябва да е положително число.', 'danger')
            return redirect(url_for('list_work_orders'))
        part = Part.query.get_or_404(int(part_id))
        if part.quantity < quantity:
            flash(f'Недостатъчна наличност за {part.name}.', 'danger')
            return redirect(url_for('list_work_orders'))
        link = WorkOrderPart.query.filter_by(work_order_id=order.id, part_id=part.id).first()
        if link:
            link.quantity_used += quantity
        else:
            link = WorkOrderPart(work_order_id=order.id, part_id=part.id, quantity_used=quantity, unit_price_snapshot=part.unit_price)
            db.session.add(link)
        part.quantity -= quantity
        if order.mechanic_id is None and current_user.role == 'mechanic':
            order.mechanic_id = current_user.id
        db.session.commit()
        flash('Частта е добавена към поръчката.', 'success')
        return redirect(url_for('list_work_orders', status=request.args.get('status', ''), q=request.args.get('q', '')))

    @app.route('/work-orders/<int:order_id>/pdf')
    @login_required
    def work_order_pdf(order_id):
        order = WorkOrder.query.get_or_404(order_id)
        if not order_access_allowed(order):
            flash('Нямате достъп до тази поръчка.', 'danger')
            return redirect(url_for('list_work_orders'))

        font_candidates = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        ]
        font_name = 'Helvetica'
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                    font_name = 'DejaVuSans'
                    break
                except Exception:
                    pass

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 50

        def line(text, size=11, gap=18, bold=False):
            nonlocal y
            if y < 60:
                c.showPage()
                y = height - 50
            c.setFont(font_name, size)
            c.drawString(50, y, str(text))
            y -= gap

        c.setTitle(f'work_order_{order.id}.pdf')
        line('Сервизна поръчка', size=18)
        line(f'Номер: #{order.id}')
        line(f'Дата: {order.created_at.strftime("%d.%m.%Y %H:%M")}')
        line('')
        line(f'Статус: {status_label(order.status)}')
        line(f'Автомобил: {order.car.make} {order.car.model}')
        line(f'Рег. номер: {order.car.registration_number or "-"}')
        line(f'VIN: {order.car.vin}')
        line(f'Собственик: {order.car.owner_name}')
        line(f'Телефон: {order.car.owner_phone or "-"}')
        line('')
        line(f'Заглавие: {order.title}')
        line(f'Описание: {order.description}')
        line(f'Бележки: {order.notes or "-"}')
        line(f'Механик: {order.mechanic.username if order.mechanic else "-"}')
        line('')
        line('Използвани части:', size=13)
        if order.parts:
            for link in order.parts:
                line(f'- {link.part.name}: {link.quantity_used} x {link.unit_price_snapshot:.2f} лв. = {(link.quantity_used * link.unit_price_snapshot):.2f} лв.')
        else:
            line('- Няма добавени части.')
        line('')
        line(f'Цена труд: {order.labor_cost:.2f} лв.', size=12)
        line(f'Цена части: {order.total_parts_cost:.2f} лв.', size=12)
        line(f'Обща цена: {order.total_cost:.2f} лв.', size=13)
        c.save()
        buffer.seek(0)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'work_order_{order.id}.pdf')

    @app.route('/work-orders/<int:order_id>/delete', methods=['POST'])
    @role_required('manager')
    def delete_work_order(order_id):
        order = WorkOrder.query.get_or_404(order_id)
        for link in order.parts:
            link.part.quantity += link.quantity_used
        db.session.delete(order)
        db.session.commit()
        flash('Работната поръчка е изтрита.', 'info')
        return redirect(url_for('list_work_orders', status=request.args.get('status', ''), q=request.args.get('q', '')))

    @app.route('/users', methods=['GET', 'POST'])
    @role_required('manager')
    def manage_users():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'client').strip()
            full_name = request.form.get('full_name', '').strip()
            phone = normalize_phone(request.form.get('phone', ''))
            if not username or not password:
                flash('Потребителско име и парола са задължителни.', 'danger')
                return redirect(url_for('manage_users'))
            if role not in {'manager', 'mechanic', 'client'}:
                flash('Невалидна роля.', 'danger')
                return redirect(url_for('manage_users'))
            if User.query.filter_by(username=username).first():
                flash('Това потребителско име вече съществува.', 'danger')
                return redirect(url_for('manage_users'))
            user = User(username=username, role=role, full_name=full_name, phone=phone)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Потребителят е създаден.', 'success')
            return redirect(url_for('manage_users'))
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('users.html', users=users)

    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @role_required('manager')
    def delete_user(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('Не можете да изтриете текущия си акаунт.', 'danger')
            return redirect(url_for('manage_users'))
        db.session.delete(user)
        db.session.commit()
        flash('Потребителят е изтрит.', 'info')
        return redirect(url_for('manage_users'))

    @app.route('/reports')
    @role_required('manager')
    def reports():
        low_stock_parts = Part.query.filter(Part.quantity <= Part.min_quantity).order_by(Part.quantity.asc()).all()
        completed_orders = WorkOrder.query.filter_by(status='completed').all()
        monthly_income = round(sum(order.total_cost for order in completed_orders), 2)
        status_counts = {code: WorkOrder.query.filter_by(status=code).count() for code in ALLOWED_WORK_ORDER_STATUSES}
        total_orders = sum(status_counts.values())
        total_parts_value = round(sum((part.quantity or 0) * (part.unit_price or 0) for part in Part.query.all()), 2)
        average_order_value = round((sum(order.total_cost for order in completed_orders) / len(completed_orders)), 2) if completed_orders else 0
        return render_template(
            'reports.html',
            low_stock_parts=low_stock_parts,
            monthly_income=monthly_income,
            status_counts=status_counts,
            total_orders=total_orders,
            total_parts_value=total_parts_value,
            average_order_value=average_order_value,
        )
