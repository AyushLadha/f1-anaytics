# fix_driver_codes.py
import db

con = db.connect()
result = con.execute("UPDATE drivers SET code = NULL WHERE code = 'nan'")
print(f"updated {result.fetchall()} rows; affected drivers now have NULL code")
con.close()