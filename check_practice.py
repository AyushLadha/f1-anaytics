import db

con = db.connect(read_only=True)

# Distinct codes that appear in practice_pace but NOT in drivers.code
print("=== practice_pace codes missing from drivers table ===")
missing = con.execute("""
    SELECT DISTINCT pp.driver_id AS code
    FROM practice_pace pp
    LEFT JOIN drivers d ON d.code = pp.driver_id
    WHERE d.code IS NULL
""").df()
print(missing if not missing.empty else "(none — all codes mappable)")

# Distinct codes in drivers that never appear in practice_pace
print("\n=== drivers in `drivers` table with no practice_pace rows ===")
unused = con.execute("""
    SELECT DISTINCT d.driver_id, d.code
    FROM drivers d
    LEFT JOIN practice_pace pp ON pp.driver_id = d.code
    WHERE pp.driver_id IS NULL
""").df()
print(unused if not unused.empty else "(none)")

con.close()