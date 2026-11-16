-- Normalised schema for KazakhLawCorpus-clean (3NF star: act + dimensions + M:N bridges)
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS act_area;
DROP TABLE IF EXISTS act_form;
DROP TABLE IF EXISTS act;
DROP TABLE IF EXISTS body;
DROP TABLE IF EXISTS region;
DROP TABLE IF EXISTS legal_force;
DROP TABLE IF EXISTS section;
DROP TABLE IF EXISTS area;
DROP TABLE IF EXISTS form;

CREATE TABLE body (
    body_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    short_name  TEXT NOT NULL,
    body_type   TEXT NOT NULL
);

CREATE TABLE region (
    region_id    INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    short_name   TEXT NOT NULL,
    region_level TEXT NOT NULL
);

CREATE TABLE legal_force (
    legal_force_id  INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    short_name      TEXT NOT NULL,
    authority_level TEXT NOT NULL
);

CREATE TABLE section (
    section_id INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE
);

CREATE TABLE area (
    area_id INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE form (
    form_id INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE act (
    act_id          INTEGER PRIMARY KEY,
    law_id          TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    date_adopted    TEXT NOT NULL,
    adoption_year   INTEGER NOT NULL,
    adoption_month  INTEGER NOT NULL,
    date_modified   TEXT,
    date_published  TEXT,
    is_repealed     INTEGER NOT NULL CHECK (is_repealed IN (0, 1)),
    adilet_url      TEXT,
    body_id         INTEGER REFERENCES body(body_id),
    region_id       INTEGER REFERENCES region(region_id),
    legal_force_id  INTEGER REFERENCES legal_force(legal_force_id),
    section_id      INTEGER REFERENCES section(section_id)
);

CREATE TABLE act_area (
    act_id  INTEGER NOT NULL REFERENCES act(act_id),
    area_id INTEGER NOT NULL REFERENCES area(area_id),
    PRIMARY KEY (act_id, area_id)
);

CREATE TABLE act_form (
    act_id  INTEGER NOT NULL REFERENCES act(act_id),
    form_id INTEGER NOT NULL REFERENCES form(form_id),
    PRIMARY KEY (act_id, form_id)
);

CREATE INDEX idx_act_year        ON act(adoption_year);
CREATE INDEX idx_act_date        ON act(date_adopted);
CREATE INDEX idx_act_body        ON act(body_id);
CREATE INDEX idx_act_region      ON act(region_id);
CREATE INDEX idx_act_force       ON act(legal_force_id);
CREATE INDEX idx_act_section     ON act(section_id);
CREATE INDEX idx_act_repealed    ON act(is_repealed);
CREATE INDEX idx_act_area_area   ON act_area(area_id);
CREATE INDEX idx_act_form_form   ON act_form(form_id);
CREATE INDEX idx_region_level    ON region(region_level);
CREATE INDEX idx_force_authority ON legal_force(authority_level);
