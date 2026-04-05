ALTER TABLE orders
ADD COLUMN status TINYTEXT NOT NULL DEFAULT 'draft';
UPDATE orders
SET status = 'draft';