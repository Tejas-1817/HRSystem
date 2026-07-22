-- Add renewal_date to devices table
SELECT COUNT(*) INTO @col_exists
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'devices' 
AND COLUMN_NAME = 'renewal_date';

SET @query = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN renewal_date DATE NULL AFTER rental_end_date',
    'SELECT "Column renewal_date already exists."');

PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add index on renewal_date
SELECT COUNT(*) INTO @idx_exists_renewal
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
AND TABLE_NAME = 'devices'
AND INDEX_NAME = 'idx_device_renewal_date';

SET @query_idx_renewal = IF(@idx_exists_renewal = 0,
    'ALTER TABLE devices ADD INDEX idx_device_renewal_date (renewal_date)',
    'SELECT "Index idx_device_renewal_date already exists."');

PREPARE stmt_idx_renewal FROM @query_idx_renewal;
EXECUTE stmt_idx_renewal;
DEALLOCATE PREPARE stmt_idx_renewal;

-- Add composite index on ownership_type and rental_cost_frequency
SELECT COUNT(*) INTO @idx_exists_rentals
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
AND TABLE_NAME = 'devices'
AND INDEX_NAME = 'idx_device_rentals';

SET @query_idx_rentals = IF(@idx_exists_rentals = 0,
    'ALTER TABLE devices ADD INDEX idx_device_rentals (ownership_type, rental_cost_frequency)',
    'SELECT "Index idx_device_rentals already exists."');

PREPARE stmt_idx_rentals FROM @query_idx_rentals;
EXECUTE stmt_idx_rentals;
DEALLOCATE PREPARE stmt_idx_rentals;
