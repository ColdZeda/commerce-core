-- 应用账号还要能建/删 pytest 用的测试库，否则容器 MySQL 上跑不起用例。
-- 库名固定 test_ + MYSQL_DATABASE，与 config/settings/test.py 的默认值一致。
GRANT ALL PRIVILEGES ON `test_commerce`.* TO 'commerce'@'%';
FLUSH PRIVILEGES;
