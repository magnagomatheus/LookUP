CREATE TABLE IF NOT EXISTS User (
    id INTEGER AUTOINCREMENT,
    name VARCHAR[75] NOT NULL,
    email VARCHAR[100] UNIQUE NOT NULL,
    password VARCHAR[150] NOT NULL,

    PRIMARY KEY (id)
);


CREATE TABLE IF NOT EXISTS Country (
    id INTEGER AUTOINCREMENT,
    name VARCHAR[150] NOT NULL,

    PRIMARY KEY(id)
);

CREATE TABLE IF NOT EXISTS State_address (
    id INTEGER AUTOINCREMENT,
    name VARCHAR[150] NOT NULL,
    fk_country INTEGER NOT NULL,

    PRIMARY KEY(id),
    FOREIGN KEY (fk_country) references Country(id)
);

CREATE TABLE IF NOT EXISTS City (
    id INTEGER AUTOINCREMENT,
    name VARCHAR[150] NOT NULL,
    fk_state INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (fk_state) references State_address(id)
);

CREATE TABLE IF NOT EXISTS User_address (
    id INTEGER AUTOINCREMENT
    latitude DECIMAL(8, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    fk_user INTEGER NOT NULL,
    fk_city INTEGER NOT NULL,

    PRIMARY KEY (id),

    FOREIGN KEY(fk_user) references User(id),
    FOREIGN KEY(fk_city) references City(id)
);
