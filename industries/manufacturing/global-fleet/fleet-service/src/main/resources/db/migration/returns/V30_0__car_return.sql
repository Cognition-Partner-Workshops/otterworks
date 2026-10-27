-- Returns context (GF14-GF18): one return per closed assignment, carrying the
-- odometer reading in the profile distance unit.
CREATE TABLE car_return (
    id              BIGSERIAL     PRIMARY KEY,
    assignment_id   BIGINT        NOT NULL REFERENCES assignment(id),
    vehicle_id      BIGINT        NOT NULL REFERENCES vehicle(id),
    return_date     DATE          NOT NULL,
    odometer        INTEGER       NOT NULL CHECK (odometer >= 0),
    condition_note  VARCHAR(200),
    CONSTRAINT car_return_assignment_key UNIQUE (assignment_id)
);

CREATE INDEX car_return_vehicle_latest ON car_return (vehicle_id, return_date DESC, id DESC);
