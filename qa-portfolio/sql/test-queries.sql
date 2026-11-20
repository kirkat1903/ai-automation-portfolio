-- Дубли email
SELECT email, COUNT(*) AS duplicate_count
FROM users
GROUP BY email
HAVING COUNT(*) > 1;

-- Пустые обязательные данные
SELECT * FROM users
WHERE full_name IS NULL OR TRIM(full_name) = '';

-- Задачи без пользователя
SELECT t.*
FROM tasks t
LEFT JOIN users u ON u.id = t.user_id
WHERE u.id IS NULL;

-- Недопустимые статусы
SELECT * FROM tasks
WHERE status NOT IN ('new', 'in_progress', 'done', 'cancelled')
   OR status IS NULL;

-- Количество задач по пользователям
SELECT u.id, u.email, COUNT(t.id) AS task_count
FROM users u
LEFT JOIN tasks t ON t.user_id = u.id
GROUP BY u.id, u.email
ORDER BY u.id;

-- Дубли первичного ключа: ожидается 0 строк
SELECT id, COUNT(*)
FROM tasks
GROUP BY id
HAVING COUNT(*) > 1;

-- Сверка агрегата статусов
SELECT status, COUNT(*) AS total
FROM tasks
GROUP BY status
ORDER BY status;

