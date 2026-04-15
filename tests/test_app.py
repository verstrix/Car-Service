import tempfile
import unittest
from pathlib import Path

from app import create_app, db
from app.models import Car, Part, User, WorkOrder


class CarSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / 'test.sqlite3'
        self.app = create_app(
            {
                'TESTING': True,
                'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path.as_posix()}',
                'SEED_DATABASE': True,
            },
            instance_path=self.temp_dir.name,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.client = None
        self.app = None
        self.temp_dir.cleanup()

    def login(self, username, password):
        return self.client.post(
            '/login',
            data={'username': username, 'password': password},
            follow_redirects=True,
        )

    def test_mechanic_cannot_create_work_order(self):
        with self.app.app_context():
            before = WorkOrder.query.count()

        self.login('mechanic', 'mechanic123')
        response = self.client.post(
            '/work-orders',
            data={'title': 'Unauthorized', 'description': 'Should fail', 'car_id': '1'},
            follow_redirects=True,
        )

        with self.app.app_context():
            after = WorkOrder.query.count()

        self.assertEqual(before, after)
        self.assertIn('Само мениджър или клиент може да създава работни поръчки.', response.get_data(as_text=True))

    def test_client_order_is_created_without_mechanic_and_with_open_status(self):
        self.login('client', 'client123')
        self.client.post(
            '/work-orders',
            data={
                'title': 'Client request',
                'description': 'Need inspection',
                'car_id': '1',
                'mechanic_id': '2',
                'status': 'completed',
            },
            follow_redirects=True,
        )

        with self.app.app_context():
            order = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
            client = User.query.filter_by(username='client').first()

        self.assertEqual(order.title, 'Client request')
        self.assertEqual(order.status, 'open')
        self.assertIsNone(order.mechanic_id)
        self.assertEqual(order.client_id, client.id)

    def test_blank_phone_client_cannot_see_unlinked_blank_phone_car(self):
        with self.app.app_context():
            user = User(username='blankclient', role='client', phone='')
            user.set_password('blankpass')
            car = Car(
                vin='WVWZZZ1JZXW000001',
                make='VW',
                model='HiddenCar',
                owner_name='Anonymous',
                owner_phone='',
                registration_number='XX0000XX',
            )
            db.session.add_all([user, car])
            db.session.commit()
            car_id = car.id

        self.login('blankclient', 'blankpass')
        list_response = self.client.get('/cars')
        details_response = self.client.get(f'/cars/{car_id}', follow_redirects=True)

        self.assertNotIn('HiddenCar', list_response.get_data(as_text=True))
        self.assertIn('Нямате достъп до този автомобил.', details_response.get_data(as_text=True))

    def test_cannot_delete_car_with_existing_orders(self):
        self.login('manager', 'manager123')
        self.client.post('/cars/1/delete', follow_redirects=True)

        with self.app.app_context():
            car = db.session.get(Car, 1)

        self.assertIsNotNone(car)

    def test_cannot_delete_part_used_in_order(self):
        self.login('manager', 'manager123')
        self.client.post('/parts/2/delete', follow_redirects=True)

        with self.app.app_context():
            part = db.session.get(Part, 2)

        self.assertIsNotNone(part)

    def test_cannot_delete_user_with_related_records(self):
        self.login('manager', 'manager123')
        self.client.post('/users/2/delete', follow_redirects=True)

        with self.app.app_context():
            mechanic = db.session.get(User, 2)

        self.assertIsNotNone(mechanic)

    def test_reports_monthly_income_ignores_old_completed_orders(self):
        with self.app.app_context():
            current_order = db.session.get(WorkOrder, 1)
            current_order.status = 'completed'
            current_order.labor_cost = 100

            old_order = WorkOrder(
                title='Old completed',
                description='Archived order',
                status='completed',
                labor_cost=40,
                car_id=1,
                client_id=3,
                mechanic_id=2,
                created_by_id=1,
            )
            db.session.add(old_order)
            db.session.flush()
            old_order.created_at = old_order.created_at.replace(year=old_order.created_at.year - 1)
            old_order.updated_at = old_order.updated_at.replace(year=old_order.updated_at.year - 1)
            db.session.commit()

        self.login('manager', 'manager123')
        response = self.client.get('/reports')
        html = response.get_data(as_text=True)

        self.assertIn('114.50', html)
        self.assertNotIn('154.50', html)


if __name__ == '__main__':
    unittest.main()
