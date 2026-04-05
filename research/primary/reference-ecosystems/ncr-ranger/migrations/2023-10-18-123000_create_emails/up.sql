CREATE TABLE emails (
    id BINARY(16) NOT NULL,
    exercise_id BINARY(16) NOT NULL,
    user_id TEXT,
    from_address TEXT NOT NULL,
    to_addresses TEXT NOT NULL,
    reply_to_addresses TEXT,
    cc_addresses TEXT,
    bcc_addresses TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (exercise_id) REFERENCES exercises(id)
);

CREATE TABLE email_statuses (
    id BINARY(16) NOT NULL,
    email_id BINARY(16) NOT NULL,
    name TINYTEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);
