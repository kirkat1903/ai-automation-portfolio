-- Учебная схема. Не содержит данных работодателя.
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(20),
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO users VALUES
(1, 'anna@example.test', 'Anna Ivanova', CURRENT_TIMESTAMP),
(2, 'boris@example.test', NULL, CURRENT_TIMESTAMP),
(3, 'anna@example.test', 'Duplicate Email', CURRENT_TIMESTAMP);

INSERT INTO tasks VALUES
(1, 1, 'Prepare test cases', 'done', CURRENT_TIMESTAMP),
(2, 1, 'Run regression', 'in_progress', CURRENT_TIMESTAMP),
(3, 999, 'Orphan task', 'new', CURRENT_TIMESTAMP),
(4, 2, 'Invalid status', 'unknown', CURRENT_TIMESTAMP);

