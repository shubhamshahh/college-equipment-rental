# 📦 CampusParcel — Campus Parcel Delivery Platform

A Porter/Dunzo-style parcel delivery web app for colleges and schools.
Senders create a delivery order with a pickup address and a drop address
(picked on Google Maps), nearby riders accept and deliver it, and both
pickup and drop are OTP-verified.

## Tech Stack
- **Frontend:** HTML, CSS, Bootstrap 5, vanilla JavaScript, Google Maps JavaScript API + Places Autocomplete
- **Backend:** Python + Flask
- **Database:** MySQL

## Roles
- **Sender** — places parcel orders (pickup → drop), tracks delivery, rates the rider
- **Rider** — goes online/offline, accepts available orders, updates delivery status, verifies OTPs
- **Admin** — views platform-wide stats and all orders

## Features
- Pickup & drop location selection via **Google Maps** (click to drop a pin, drag the marker, or search with Places Autocomplete)
- **Distance-based fare**: flat base fee + ₹/km rate, calculated automatically using the Haversine formula
- Live fare estimate shown to the sender before placing the order
- Rider dashboard: toggle online/offline, view available orders, accept orders
- Full delivery lifecycle: `pending → accepted → arrived_pickup → picked_up → in_transit → arrived_drop → delivered`
- **OTP verification** at both pickup (sender's OTP) and drop (receiver's OTP) so the parcel only changes hands with the right person
- QR code generated per order (for additional verification/printing)
- Status timeline log for every order
- Sender can rate the rider after delivery
- Admin dashboard with order stats and revenue

## Setup Instructions

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up MySQL database
```bash
mysql -u root -p < schema.sql
```

### 3. Configure database credentials
Edit `app.py` and update `DB_CONFIG`:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_mysql_password",
    "database": "parcel_delivery_db",
}
```

### 4. Get a Google Maps API key
1. Go to https://console.cloud.google.com/
2. Create a project (or use an existing one)
3. Enable **Maps JavaScript API** and **Places API**
4. Create an API key (restrict it to your domain/localhost for safety)
5. Paste it into `app.py`:
```python
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"
```
> The free tier includes $200/month credit, which covers a large number of
> map loads — more than enough for a college project/demo.

### 5. Set your campus coordinates & pricing
In `app.py`:
```python
DEFAULT_LAT = 22.4707     # your college's latitude
DEFAULT_LNG = 70.0577     # your college's longitude
BASE_FEE = 15.0           # flat pickup fee
RATE_PER_KM = 8.0         # fare per kilometre
```

### 6. Run the app
```bash
python app.py
```
Visit `http://127.0.0.1:5000`.

## How a Delivery Works (end to end)
1. **Sender** logs in, goes to "Send a Parcel", fills in parcel details,
   and picks pickup + drop locations on two separate maps (search or
   click/drag). The fare estimate updates live as locations change.
2. On placing the order, the app calculates `distance_km` using the
   Haversine formula and stores `base_fee + distance_fee = total_fare`.
   A unique `order_ref`, a 6-digit **pickup OTP**, and a 6-digit
   **drop OTP** are generated, plus a QR code.
3. **Riders** who are online see the order appear in "Available Orders
   Nearby" and can accept it.
4. The rider moves the order through statuses: arrived at pickup → enters
   the **pickup OTP** (given by the sender) to mark it picked up → in
   transit → arrived at drop → enters the **drop OTP** (given by the
   receiver) to mark it delivered.
5. Once delivered, the sender can rate the rider.

## Project Structure
```
parcel_delivery/
├── app.py                     # Flask application (all routes)
├── schema.sql                 # MySQL schema
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── home.html               # landing page
│   ├── login.html
│   ├── register.html           # role selection: sender / rider
│   ├── send_parcel.html        # dual map picker + live fare
│   ├── sender_orders.html
│   ├── rider_dashboard.html    # online/offline + available orders
│   ├── order_detail.html       # tracking, OTP entry, route map, timeline
│   └── admin_dashboard.html
└── static/
    ├── css/style.css
    ├── js/main.js
    └── uploads/qrcodes/
```

## Notes / Possible Extensions
- Add real-time rider location tracking (e.g. periodic geolocation pings + WebSocket/polling on the tracking map).
- Restrict order visibility to riders within a certain radius of the pickup point (currently all online riders see all pending orders).
- Add online payment integration (Razorpay/Stripe) instead of cash-on-delivery style fare.
- Add push/SMS notifications for order status changes.
- Add a proper roads-based distance/ETA using the Google Distance Matrix API instead of straight-line Haversine distance.
