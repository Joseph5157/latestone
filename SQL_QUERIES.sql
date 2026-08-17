-- ============================================================================
-- SQL QUERIES for PowerPlant Dashboard
-- ============================================================================
-- Database: powerplant_demo
-- Schema: plant_monitoring
-- Run these with: docker exec plant_monitoring_postgres psql -U powerplant -d powerplant_demo -c "YOUR_QUERY" -P pager=off

-- ============================================================================
-- DATABASE & SCHEMA INFO
-- ============================================================================

-- List all databases (non-template)
SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;

-- List all schemas in current database
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name NOT IN ('pg_catalog', 'information_schema') 
ORDER BY schema_name;

-- List all tables in plant_monitoring schema
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'plant_monitoring' 
ORDER BY table_name;

-- ============================================================================
-- DATA OVERVIEW
-- ============================================================================

-- Row counts for all tables
SELECT 
  tablename,
  (SELECT COUNT(*) FROM plant_monitoring.plants) as plants,
  (SELECT COUNT(*) FROM plant_monitoring.transformers) as transformers,
  (SELECT COUNT(*) FROM plant_monitoring.devices) as devices,
  (SELECT COUNT(*) FROM plant_monitoring.readings) as readings;

-- Alternative: view each table's size
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  (SELECT COUNT(*) FROM (SELECT 1 FROM plant_monitoring.plants LIMIT 1) t) as plants,
  (SELECT COUNT(*) FROM (SELECT 1 FROM plant_monitoring.transformers LIMIT 1) t) as transformers,
  (SELECT COUNT(*) FROM (SELECT 1 FROM plant_monitoring.devices LIMIT 1) t) as devices,
  (SELECT COUNT(*) FROM (SELECT 1 FROM plant_monitoring.readings LIMIT 1) t) as readings
FROM pg_tables 
WHERE schemaname = 'plant_monitoring';

-- ============================================================================
-- PLANTS TABLE
-- ============================================================================

-- List all 30 plants
SELECT id, name, country, latitude, longitude 
FROM plant_monitoring.plants 
ORDER BY id;

-- Count plants
SELECT COUNT(*) as total_plants FROM plant_monitoring.plants;

-- ============================================================================
-- TRANSFORMERS TABLE
-- ============================================================================

-- List all transformers with their plant names
SELECT 
  t.id,
  t.plant_id,
  p.name as plant_name,
  t.transformer_id
FROM plant_monitoring.transformers t
JOIN plant_monitoring.plants p ON t.plant_id = p.id
ORDER BY t.plant_id, t.id;

-- Count transformers per plant
SELECT 
  p.id as plant_id,
  p.name as plant_name,
  COUNT(t.id) as transformer_count
FROM plant_monitoring.plants p
LEFT JOIN plant_monitoring.transformers t ON p.id = t.plant_id
GROUP BY p.id, p.name
ORDER BY p.id;

-- Count total transformers
SELECT COUNT(*) as total_transformers FROM plant_monitoring.transformers;

-- ============================================================================
-- DEVICES TABLE
-- ============================================================================

-- List all devices
SELECT 
  d.id,
  d.plant_id,
  d.transformer_id,
  d.device_id,
  p.name as plant_name
FROM plant_monitoring.devices d
JOIN plant_monitoring.plants p ON d.plant_id = p.id
ORDER BY d.plant_id, d.transformer_id, d.id;

-- Count devices per transformer
SELECT 
  t.id as transformer_id,
  t.plant_id,
  COUNT(d.id) as device_count
FROM plant_monitoring.transformers t
LEFT JOIN plant_monitoring.devices d ON t.id = d.transformer_id
GROUP BY t.id, t.plant_id
ORDER BY t.plant_id, t.id;

-- Count total devices
SELECT COUNT(*) as total_devices FROM plant_monitoring.devices;

-- ============================================================================
-- READINGS TABLE
-- ============================================================================

-- Row count
SELECT COUNT(*) as total_readings FROM plant_monitoring.readings;

-- Count readings per metric
SELECT 
  metric,
  COUNT(*) as reading_count
FROM plant_monitoring.readings
GROUP BY metric
ORDER BY metric;

-- Count readings per device
SELECT 
  device_id,
  COUNT(*) as reading_count,
  MIN(reading_ts) as earliest,
  MAX(reading_ts) as latest
FROM plant_monitoring.readings
GROUP BY device_id
ORDER BY device_id;

-- Sample readings from a specific device
SELECT device_id, metric, reading_ts, value 
FROM plant_monitoring.readings 
WHERE device_id = 'plant-01-t1-d1'  -- Example device
ORDER BY metric, reading_ts DESC 
LIMIT 20;

-- Date range of readings
SELECT 
  MIN(reading_ts) as earliest_reading,
  MAX(reading_ts) as latest_reading,
  COUNT(*) as total_readings
FROM plant_monitoring.readings;

-- Readings per day
SELECT 
  DATE(reading_ts) as reading_date,
  COUNT(*) as reading_count
FROM plant_monitoring.readings
GROUP BY DATE(reading_ts)
ORDER BY reading_date DESC
LIMIT 10;

-- ============================================================================
-- HIERARCHY QUERIES
-- ============================================================================

-- Complete hierarchy: Plant -> Transformer -> Device
SELECT 
  p.id as plant_id,
  p.name as plant_name,
  t.id as transformer_id,
  d.id as device_id,
  d.device_id as device_name
FROM plant_monitoring.plants p
LEFT JOIN plant_monitoring.transformers t ON p.id = t.plant_id
LEFT JOIN plant_monitoring.devices d ON t.id = d.transformer_id
ORDER BY p.id, t.id, d.id;

-- Hierarchy summary with counts
SELECT 
  p.id as plant_id,
  p.name as plant_name,
  COUNT(DISTINCT t.id) as transformer_count,
  COUNT(DISTINCT d.id) as device_count
FROM plant_monitoring.plants p
LEFT JOIN plant_monitoring.transformers t ON p.id = t.plant_id
LEFT JOIN plant_monitoring.devices d ON t.id = d.transformer_id
GROUP BY p.id, p.name
ORDER BY p.id;

-- ============================================================================
-- METRIC ANALYSIS
-- ============================================================================

-- List all available metrics
SELECT DISTINCT metric FROM plant_monitoring.readings ORDER BY metric;

-- Statistics per metric (min, max, avg, latest)
SELECT 
  metric,
  COUNT(*) as reading_count,
  MIN(CAST(value AS FLOAT)) as min_value,
  MAX(CAST(value AS FLOAT)) as max_value,
  AVG(CAST(value AS FLOAT)) as avg_value,
  STDDEV(CAST(value AS FLOAT)) as stddev_value
FROM plant_monitoring.readings
GROUP BY metric
ORDER BY metric;

-- Latest reading for each metric for a device
SELECT 
  device_id,
  metric,
  value,
  reading_ts
FROM plant_monitoring.readings
WHERE device_id = 'plant-01-t1-d1'  -- Example device
  AND (device_id, metric, reading_ts) IN (
    SELECT device_id, metric, MAX(reading_ts)
    FROM plant_monitoring.readings
    WHERE device_id = 'plant-01-t1-d1'
    GROUP BY device_id, metric
  )
ORDER BY metric;

-- ============================================================================
-- TABLE STRUCTURE
-- ============================================================================

-- Show column information for plants table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema = 'plant_monitoring' AND table_name = 'plants';

-- Show column information for transformers table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema = 'plant_monitoring' AND table_name = 'transformers';

-- Show column information for devices table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema = 'plant_monitoring' AND table_name = 'devices';

-- Show column information for readings table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema = 'plant_monitoring' AND table_name = 'readings';

-- ============================================================================
-- USEFUL COMMANDS (psql)
-- ============================================================================

-- These work in interactive psql shell (docker exec -it ... psql):
-- \dt plant_monitoring.*       - list all tables in schema
-- \d plant_monitoring.plants   - describe plants table
-- \d plant_monitoring.readings - describe readings table
-- \l                            - list all databases
-- \dn                           - list all schemas
-- \q                            - quit
