-- ==============================================
-- Airbnb Data Warehouse - Database Schema
-- ==============================================
-- Author: Shazil
-- Description: Star Schema for Airbnb Listings Data Warehouse
-- Database: airbnb_dwh
-- Tables: 5 Dimension Tables + 1 Fact Table
-- ==============================================

-- Create Database
CREATE DATABASE IF NOT EXISTS airbnb_dwh;
USE airbnb_dwh;

-- ==============================================
-- DIMENSION TABLES
-- ==============================================

-- Dimension Table: Listing
DROP TABLE IF EXISTS dim_listing;
CREATE TABLE dim_listing (
    listing_id BIGINT PRIMARY KEY,
    listing_name TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dimension Table: Host
DROP TABLE IF EXISTS dim_host;
CREATE TABLE dim_host (
    host_id BIGINT PRIMARY KEY,
    host_name TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dimension Table: Location
DROP TABLE IF EXISTS dim_location;
CREATE TABLE dim_location (
    neighbourhood_id BIGINT PRIMARY KEY,
    neighbourhood_group TEXT,
    neighbourhood TEXT,
    latitude DOUBLE,
    longitude DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dimension Table: Room Type
DROP TABLE IF EXISTS dim_room;
CREATE TABLE dim_room (
    room_type_id BIGINT PRIMARY KEY,
    room_type TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dimension Table: Date
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_id BIGINT PRIMARY KEY,
    last_review DATETIME,
    year BIGINT,
    month BIGINT,
    day BIGINT,
    weekday TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==============================================
-- FACT TABLE
-- ==============================================

-- Fact Table: Listing Facts
DROP TABLE IF EXISTS fact_listing;
CREATE TABLE fact_listing (
    listing_id BIGINT,
    host_id BIGINT,
    neighbourhood_id BIGINT,
    room_type_id BIGINT,
    date_id BIGINT,
    price DOUBLE,
    minimum_nights BIGINT,
    number_of_reviews BIGINT,
    reviews_per_month DOUBLE,
    calculated_host_listings_count BIGINT,
    availability_365 BIGINT,
    
    -- Foreign Key Constraints
    FOREIGN KEY (listing_id) REFERENCES dim_listing(listing_id),
    FOREIGN KEY (host_id) REFERENCES dim_host(host_id),
    FOREIGN KEY (neighbourhood_id) REFERENCES dim_location(neighbourhood_id),
    FOREIGN KEY (room_type_id) REFERENCES dim_room(room_type_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    
    -- Indexes for better query performance
    INDEX idx_listing (listing_id),
    INDEX idx_host (host_id),
    INDEX idx_location (neighbourhood_id),
    INDEX idx_room (room_type_id),
    INDEX idx_date (date_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==============================================
-- SAMPLE QUERIES
-- ==============================================

-- Query 1: Total listings by neighbourhood group
-- SELECT 
--     l.neighbourhood_group,
--     COUNT(*) as total_listings,
--     AVG(f.price) as avg_price
-- FROM fact_listing f
-- JOIN dim_location l ON f.neighbourhood_id = l.neighbourhood_id
-- GROUP BY l.neighbourhood_group;

-- Query 2: Average price by room type
-- SELECT 
--     r.room_type,
--     COUNT(*) as total_listings,
--     AVG(f.price) as avg_price,
--     MIN(f.price) as min_price,
--     MAX(f.price) as max_price
-- FROM fact_listing f
-- JOIN dim_room r ON f.room_type_id = r.room_type_id
-- GROUP BY r.room_type;

-- Query 3: Top 10 hosts by number of listings
-- SELECT 
--     h.host_name,
--     COUNT(*) as total_listings,
--     AVG(f.price) as avg_price
-- FROM fact_listing f
-- JOIN dim_host h ON f.host_id = h.host_id
-- GROUP BY h.host_id, h.host_name
-- ORDER BY total_listings DESC
-- LIMIT 10;

-- Query 4: Listings trend by month
-- SELECT 
--     d.year,
--     d.month,
--     COUNT(*) as total_listings,
--     AVG(f.price) as avg_price
-- FROM fact_listing f
-- JOIN dim_date d ON f.date_id = d.date_id
-- WHERE d.year IS NOT NULL
-- GROUP BY d.year, d.month
-- ORDER BY d.year, d.month;

-- ==============================================
-- END OF SCHEMA
-- ==============================================
