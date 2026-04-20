import os
from io import BytesIO

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from . import db
from .models import Car, Part, User, WorkOrder, WorkOrderPart
from .route_support import (
    ALLOWED_WORK_ORDER_STATUSES,
    car_access_allowed,
    client_car_filter,
    client_order_filter,
    linked_client_id_for_car,
    load_pdf_dependencies,
    order_access_allowed,
    order_edit_allowed,
    pdf_export_available,
    resolve_mechanic,
    resolve_optional_int,
    role_required,
    status_label,
)


def register_work_order_routes(app):
    @app.route('/work-orders', methods=['GET', 'POST'])
    @login_required
    def list_work_orders():
        if request.method == 'POST':
            if current_user.role not in {'manager', 'client'}:
                flash('Само мениджър или клиент може да създава работни поръчки.', 'danger')
                return redirect(url_for('list_work_orders'))

            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            car_id, car_id_error = resolve_optional_int(request.form.get('car_id'), 'автомобил')
            mechanic_id, mechanic_id_error = resolve_optional_int(request.form.get('mechanic_id'), 'механик')
            labor_cost_raw = request.form.get('labor_cost', '0').strip()
            notes = request.form.get('notes', '').strip()

            if not title or not description or not car_id:
                flash('Заглавие, описание и автомобил са задължителни.', 'danger')
                return redirect(url_for('list_work_orders'))
            if car_id_error:
                flash(car_id_error, 'danger')
                return redirect(url_for('list_work_orders'))
            if mechanic_id_error:
                flash(mechanic_id_error, 'danger')
                return redirect(url_for('list_work_orders'))

            mechanic, mechanic_lookup_error = resolve_mechanic(mechanic_id)
            if mechanic_lookup_error:
                flash(mechanic_lookup_error, 'danger')
                return redirect(url_for('list_work_orders'))

            car = Car.query.get_or_404(car_id)
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
                mechanic_id=mechanic.id if current_user.role == 'manager' and mechanic else None,
                client_id=current_user.id if current_user.role == 'client' else linked_client_id_for_car(car),
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
            query = query.filter(client_order_filter(current_user))
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
            cars = Car.query.filter(client_car_filter(current_user)).order_by(Car.make.asc(), Car.model.asc()).all()
        else:
            cars = Car.query.order_by(Car.make.asc(), Car.model.asc()).all()
        mechanics = User.query.filter_by(role='mechanic').all()
        parts = Part.query.order_by(Part.name.asc()).all()

        status_counts_query = WorkOrder.query
        if current_user.role == 'mechanic':
            status_counts_query = status_counts_query.filter((WorkOrder.mechanic_id == current_user.id) | (WorkOrder.mechanic_id.is_(None)))
        elif current_user.role == 'client':
            status_counts_query = status_counts_query.join(Car).filter(client_order_filter(current_user))
        status_counts = {code: status_counts_query.filter(WorkOrder.status == code).count() for code in ALLOWED_WORK_ORDER_STATUSES}
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
            mechanic_id, mechanic_id_error = resolve_optional_int(request.form.get('mechanic_id'), 'механик')
            car_id, car_id_error = resolve_optional_int(request.form.get('car_id') or str(order.car_id), 'автомобил')

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
            if car_id_error:
                flash(car_id_error, 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))
            if mechanic_id_error:
                flash(mechanic_id_error, 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))

            mechanic, mechanic_lookup_error = resolve_mechanic(mechanic_id)
            if mechanic_lookup_error:
                flash(mechanic_lookup_error, 'danger')
                return redirect(url_for('edit_work_order', order_id=order.id))

            if current_user.role == 'manager':
                selected_car = Car.query.get_or_404(car_id)
                order.car_id = selected_car.id
                order.client_id = linked_client_id_for_car(selected_car)
                order.mechanic_id = mechanic.id if mechanic else None
            elif current_user.role == 'mechanic' and order.mechanic_id in (None, current_user.id):
                order.mechanic_id = current_user.id

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
        mechanic_id, mechanic_id_error = resolve_optional_int(request.form.get('mechanic_id'), 'механик')
        if status not in ALLOWED_WORK_ORDER_STATUSES:
            flash('Невалиден статус.', 'danger')
            return redirect(url_for('list_work_orders'))
        if mechanic_id_error:
            flash(mechanic_id_error, 'danger')
            return redirect(url_for('list_work_orders'))

        mechanic, mechanic_lookup_error = resolve_mechanic(mechanic_id)
        if mechanic_lookup_error:
            flash(mechanic_lookup_error, 'danger')
            return redirect(url_for('list_work_orders'))

        order.status = status
        if current_user.role == 'manager':
            order.mechanic_id = mechanic.id if mechanic else None
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

        part_id, part_id_error = resolve_optional_int(request.form.get('part_id'), 'част')
        quantity_raw = request.form.get('quantity_used', '1')
        if not part_id:
            flash('Изберете част.', 'danger')
            return redirect(url_for('list_work_orders'))
        if part_id_error:
            flash(part_id_error, 'danger')
            return redirect(url_for('list_work_orders'))

        try:
            quantity = int(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash('Количеството трябва да е положително число.', 'danger')
            return redirect(url_for('list_work_orders'))

        part = Part.query.get_or_404(part_id)
        if part.quantity < quantity:
            flash(f'Недостатъчна наличност за {part.name}.', 'danger')
            return redirect(url_for('list_work_orders'))

        link = WorkOrderPart.query.filter_by(work_order_id=order.id, part_id=part.id).first()
        if link:
            link.quantity_used += quantity
        else:
            link = WorkOrderPart(
                work_order_id=order.id,
                part_id=part.id,
                quantity_used=quantity,
                unit_price_snapshot=part.unit_price,
            )
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

        if not pdf_export_available():
            flash('PDF експортът е временно недостъпен. Инсталирайте reportlab, за да го използвате.', 'warning')
            return redirect(url_for('list_work_orders'))

        pdf_tools = load_pdf_dependencies()
        A4 = pdf_tools['A4']
        simpleSplit = pdf_tools['simple_split']
        pdfmetrics = pdf_tools['pdfmetrics']
        TTFont = pdf_tools['ttfont']
        canvas = pdf_tools['canvas']

        windows_font_root = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        font_candidates = [
            os.path.join(windows_font_root, 'arial.ttf'),
            os.path.join(windows_font_root, 'calibri.ttf'),
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
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 50

        def write_line(text, size=11, gap=18):
            nonlocal y
            wrapped_lines = simpleSplit(str(text), font_name, size, width - 100) or ['']
            for wrapped_line in wrapped_lines:
                if y < 60:
                    pdf.showPage()
                    y = height - 50
                pdf.setFont(font_name, size)
                pdf.drawString(50, y, wrapped_line)
                y -= gap

        pdf.setTitle(f'work_order_{order.id}.pdf')
        write_line('Сервизна поръчка', size=18)
        write_line(f'Номер: #{order.id}')
        write_line(f'Дата: {order.created_at.strftime("%d.%m.%Y %H:%M")}')
        write_line('')
        write_line(f'Статус: {status_label(order.status)}')
        write_line(f'Автомобил: {order.car.make} {order.car.model}')
        write_line(f'Рег. номер: {order.car.registration_number or "-"}')
        write_line(f'VIN: {order.car.vin}')
        write_line(f'Собственик: {order.car.owner_name}')
        write_line(f'Телефон: {order.car.owner_phone or "-"}')
        write_line('')
        write_line(f'Заглавие: {order.title}')
        write_line(f'Описание: {order.description}')
        write_line(f'Бележки: {order.notes or "-"}')
        write_line(f'Механик: {order.mechanic.username if order.mechanic else "-"}')
        write_line('')
        write_line('Използвани части:', size=13)
        if order.parts:
            for link in order.parts:
                write_line(
                    f'- {link.part.name}: {link.quantity_used} x {link.unit_price_snapshot:.2f} лв. = '
                    f'{(link.quantity_used * link.unit_price_snapshot):.2f} лв.'
                )
        else:
            write_line('- Няма добавени части.')
        write_line('')
        write_line(f'Цена труд: {order.labor_cost:.2f} лв.', size=12)
        write_line(f'Цена части: {order.total_parts_cost:.2f} лв.', size=12)
        write_line(f'Обща цена: {order.total_cost:.2f} лв.', size=13)
        pdf.save()
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
