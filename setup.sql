DROP TABLE highscore;

CREATE TABLE IF NOT EXISTS highscore
(
	id INTEGER PRIMARY KEY,
	player_name VARCHAR(255),
	score int
);

