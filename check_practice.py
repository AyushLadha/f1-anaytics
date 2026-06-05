import db

con = db.connect(read_only=True)
print(con.execute("""
    SELECT round,
           count(*) FILTER (WHERE session = 'FP1') AS fp1,
           count(*) FILTER (WHERE session = 'FP2') AS fp2,
           count(*) FILTER (WHERE session = 'FP3') AS fp3
    FROM practice_pace
    WHERE season = 2023
    GROUP BY round
    ORDER BY round
""").df())
con.close()