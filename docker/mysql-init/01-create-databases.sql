-- Create both databases
CREATE DATABASE IF NOT EXISTS `ecommerce_demo` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS `smart_analyst` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Grant permissions
GRANT ALL PRIVILEGES ON `ecommerce_demo`.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON `smart_analyst`.* TO 'root'@'%';
FLUSH PRIVILEGES;
