import sqlite3
import os

if __name__ == "__main__":
	BASE_DIR = os.path.dirname(os.path.abspath(__file__))
	database = sqlite3.connect(os.path.join(BASE_DIR, "highscore.db"))

	c = database.cursor()
	c.execute("SELECT player_name, score FROM highscore ORDER BY score DESC")

	print("platz\tname\tscore")
	for index, row in enumerate(c.fetchall()):
		print("%d\t%s\t%d" % (index+1, row[0], row[1]))
	database.close()
