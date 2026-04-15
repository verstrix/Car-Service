import os
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Моля, влезте в системата.'
login_manager.login_message_category = 'warning'


def create_app(config_overrides=None, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    os.makedirs(app.instance_path, exist_ok=True)

    upload_root = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_root, exist_ok=True)
    os.makedirs(os.path.join(upload_root, 'cars'), exist_ok=True)
    os.makedirs(os.path.join(upload_root, 'parts'), exist_ok=True)

    app.config['SECRET_KEY'] = 'diploma-car-service-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'car_service.sqlite3')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = upload_root
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config['SEED_DATABASE'] = True

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User, Car, Part, WorkOrder, WorkOrderPart

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_now():
        return {'now': datetime.now}

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('error.html', code=404, title='Страницата не е намерена', message='Адресът не съществува или ресурсът е преместен.'), 404

    @app.errorhandler(413)
    def file_too_large(error):
        return render_template('error.html', code=413, title='Файлът е твърде голям', message='Максималният размер на качваните файлове е 5 MB.'), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error.html', code=500, title='Възникна грешка', message='Системата срещна неочаквана грешка. Опитайте отново.'), 500

    from .routes import register_routes
    register_routes(app)

    with app.app_context():
        db.create_all()
        if app.config.get('SEED_DATABASE', True):
            seed_database()

    return app


def seed_database():
    from .models import User, Car, Part, WorkOrder, WorkOrderPart

    if User.query.count() > 0:
        return

    manager = User(username='manager', role='manager', full_name='Ivo Petkov', phone='0888000001')
    manager.set_password('manager123')

    mechanic = User(username='mechanic', role='mechanic', full_name='Main Mechanic', phone='0888000002')
    mechanic.set_password('mechanic123')

    client = User(username='client', role='client', full_name='Demo Client', phone='0888000003')
    client.set_password('client123')

    db.session.add_all([manager, mechanic, client])
    db.session.flush()

    car1 = Car(vin='WBA12345678900001', make='BMW', model='530d', year=2007,
               owner_name='Demo Client', owner_phone='0888000003', registration_number='VR1234AB', user_id=client.id)
    car2 = Car(vin='TMBAA73T0D9000001', make='Skoda', model='Superb', year=2013,
               owner_name='Ivan Georgiev', owner_phone='0899000001', registration_number='VR5678CD')

    part1 = Part(part_number='BRK-001', name='Brake Pads Front', quantity=12, unit_price=89.90,
                 description='Front brake pads for mid-size vehicles')
    part2 = Part(part_number='FLT-101', name='Oil Filter', quantity=30, unit_price=14.50,
                 description='Standard oil filter for diesel engines')
    part3 = Part(part_number='BLT-777', name='Timing Belt', quantity=3, unit_price=159.99,
                 description='Timing belt kit', min_quantity=4)

    db.session.add_all([car1, car2, part1, part2, part3])
    db.session.flush()

    order1 = WorkOrder(
        title='Engine diagnostics',
        description='Customer reports whistle sound while driving.',
        status='in_progress',
        labor_cost=70,
        car_id=car1.id,
        client_id=client.id,
        mechanic_id=mechanic.id,
        created_by_id=manager.id,
    )
    order2 = WorkOrder(
        title='Oil service',
        description='Regular service and filters replacement.',
        status='open',
        labor_cost=45,
        car_id=car2.id,
        created_by_id=manager.id,
    )
    db.session.add_all([order1, order2])
    db.session.flush()

    link = WorkOrderPart(work_order_id=order1.id, part_id=part2.id, quantity_used=1, unit_price_snapshot=part2.unit_price)
    part2.quantity -= 1
    db.session.add(link)
    db.session.commit()
