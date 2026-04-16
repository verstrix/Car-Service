from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import db
from .models import Car, Part, User, WorkOrder
from .route_support import ALLOWED_WORK_ORDER_STATUSES, normalize_phone, role_required


def register_admin_routes(app):
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
            if len(password) < 6:
                flash('Паролата трябва да бъде поне 6 символа.', 'danger')
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

        linked_reasons = []
        if Car.query.filter_by(user_id=user.id).first():
            linked_reasons.append('свързани автомобили')
        if WorkOrder.query.filter_by(client_id=user.id).first():
            linked_reasons.append('клиентски поръчки')
        if WorkOrder.query.filter_by(mechanic_id=user.id).first():
            linked_reasons.append('назначени поръчки')
        if WorkOrder.query.filter_by(created_by_id=user.id).first():
            linked_reasons.append('създадени поръчки')
        if linked_reasons:
            flash(f'Потребителят не може да бъде изтрит, защото има {", ".join(linked_reasons)}.', 'danger')
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
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        completed_this_month = [order for order in completed_orders if order.updated_at and order.updated_at >= start_of_month]
        monthly_income = round(sum(order.total_cost for order in completed_this_month), 2)
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
