from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from . import db
from .models import Part
from .route_support import remove_image, role_required, save_image


def register_part_routes(app):
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
        if part.order_links:
            flash('Частта не може да бъде изтрита, защото вече е използвана в работни поръчки.', 'danger')
            return redirect(url_for('list_parts'))
        remove_image(part.image_filename)
        db.session.delete(part)
        db.session.commit()
        flash('Частта е изтрита.', 'info')
        return redirect(url_for('list_parts'))
