# Database Migrations

This directory contains SQL migration scripts for the Purchase Tracker database.

## Migration Files

- `create_tables.sql` - Initial database schema creation (includes all tables)
- `insert_all_retailers.sql` - Seeds the retailers table with initial data
- `add_created_at_to_asin_bank.sql` - Adds `created_at` column to `asin_bank` table
- `alter_purchase_tracker_date_to_datetime.sql` - Changes `purchase_tracker.date` from DATE to TIMESTAMP for date & time support

## How to Apply Migrations

### For New Databases

Run the full schema creation:

```bash
psql -U your_username -d your_database -f create_tables.sql
psql -U your_username -d your_database -f insert_all_retailers.sql
```

### For Existing Databases

To add the `created_at` column to the `asin_bank` table:

```bash
psql -U your_username -d your_database -f add_created_at_to_asin_bank.sql
```

Or connect to your PostgreSQL database and run:

```sql
\i /path/to/add_created_at_to_asin_bank.sql
```

## Migration: Add created_at to asin_bank

**Date:** 2025-11-12  
**Description:** Adds a `created_at` timestamp column to the `asin_bank` table to track when each ASIN was added to the database.

**Changes:**
- Adds `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL` column
- Existing rows will have their `created_at` set to the current timestamp when the migration runs
- The migration is idempotent (safe to run multiple times)

**Impact:**
- Backend API now returns `created_at` in ASIN Bank responses
- Frontend displays the creation timestamp in the ASIN Bank table

