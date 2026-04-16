from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import Car, Part, User, WorkOrder
from .route_support import client_car_filter, client_order_filter


def register_main_routes(app):
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

        client_cars = Car.query.filter(client_car_filter(current_user)).order_by(Car.created_at.desc()).all()
        client_orders = (
            WorkOrder.query.join(Car)
            .filter(client_order_filter(current_user))
            .order_by(WorkOrder.created_at.desc())
            .all()
        )
        return render_template('dashboard_client.html', stats=stats, client_cars=client_cars, client_orders=client_orders)
