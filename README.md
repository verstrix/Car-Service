🚗 Car Service Management System
A modern web application for managing a car repair workshop.
It provides tools for handling cars, work orders, parts inventory, and user accounts — all with a clean, responsive UI.

🔧 Features
👤 Role-Based Access
Manager — full control (users, cars, parts, work orders)

Mechanic — manage assigned work orders

Client — view their cars and service history

🚘 Car Management
Add, edit, and view cars

Link cars to clients

View service history

🧰 Work Orders
Create and track work orders

Assign mechanics

Add parts used

Track status (pending, in progress, completed)

📦 Parts Inventory
Add and manage parts

Track stock levels

Use parts in work orders

👥 User Management
Create users with roles

View all existing users

Secure authentication with Flask‑Login

🎨 Modern UI
Clean, minimal design

Teal accent theme

Responsive layout using Bootstrap 5

🛠️ Tech Stack
Python 3

Flask (Blueprints, Jinja2, Flask‑Login)

SQLAlchemy

SQLite

Bootstrap 5

HTML / CSS / Jinja Templates

📂 Project Structure
Code
car_service/
│ app.py
│ config.py
│ models.py
│
├── blueprints/
│   ├── cars/
│   ├── parts/
│   ├── users/
│   └── work_orders/
│
├── templates/
├── static/
└── app.db
🚀 Getting Started
Install dependencies

Run the Flask app

Log in as manager

Start managing your workshop
