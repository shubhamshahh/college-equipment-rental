-- ============================================================
-- College Equipment Rental Marketplace - Database Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS equipment_rental_db;
USE equipment_rental_db;

-- ------------------------------------------------------------
-- USERS TABLE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    hostel_location VARCHAR(150),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- PRODUCTS TABLE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    price_per_day DECIMAL(10,2) NOT NULL,
    deposit_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    image VARCHAR(255),
    condition_status ENUM('new','good','fair','worn') DEFAULT 'good',
    status ENUM('available','rented','unavailable') DEFAULT 'available',
    pickup_location VARCHAR(150),
    delivery_available TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- BOOKINGS TABLE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    renter_id INT NOT NULL,
    owner_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days INT NOT NULL,
    rent_amount DECIMAL(10,2) NOT NULL,
    deposit_amount DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    booking_ref VARCHAR(50) NOT NULL UNIQUE,
    qr_code VARCHAR(255),
    status ENUM('confirmed','active','completed','cancelled') DEFAULT 'confirmed',

    -- Delivery related fields
    delivery_method ENUM('pickup_point','delivery') NOT NULL DEFAULT 'pickup_point',
    delivery_location VARCHAR(150),
    delivery_status ENUM(
        'pending',
        'item_dropped',
        'out_for_delivery',
        'delivered',
        'pickup_ready',
        'picked_up',
        'return_dropped',
        'return_picked_up',
        'returned_to_owner'
    ) NOT NULL DEFAULT 'pending',
    delivery_notes TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (renter_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- REVIEWS TABLE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    user_id INT NOT NULL,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- SAMPLE DATA (optional)
-- ------------------------------------------------------------
INSERT INTO users (name, email, password, phone) VALUES
('Demo User', 'demo@college.edu', 'pbkdf2:sha256:600000$placeholder$hashplaceholder', '9999999999');

-- Note: Use the app's register page to create real users with proper hashed passwords.
