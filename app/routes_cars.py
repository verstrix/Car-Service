from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from . import db
from .models import Car, User
from .route_support import (
    car_access_allowed,
    client_car_filter,
    normalize_phone,
    parse_year,
    remove_image,
    role_required,
    save_image,
)


def register_car_routes(app):
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
            query = query.filter(client_car_filter(current_user))
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
        if car.orders:
            flash('Автомобилът не може да бъде изтрит, защото има свързани работни поръчки.', 'danger')
            return redirect(url_for('list_cars'))
        remove_image(car.image_filename)
        db.session.delete(car)
        db.session.commit()
        flash('Автомобилът е изтрит.', 'info')
        return redirect(url_for('list_cars'))
