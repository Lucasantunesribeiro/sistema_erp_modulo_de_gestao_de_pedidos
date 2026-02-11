-- Grant privileges for pytest test database creation
GRANT ALL PRIVILEGES ON `test_erp_orders`.* TO 'erp_user'@'%';
FLUSH PRIVILEGES;
