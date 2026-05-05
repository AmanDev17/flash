from flash import FlashDB

# ── Change this to your DB ──
flash = FlashDB("mysql", {
    "host":     "localhost",
    "user":     "root",
    "password": "your_password",
    "database": "test_db"
})

# 1. Ping
print("Connected:", flash.ping())

# 2. Create table
flash.create_table("users", {
    "id":    "int",
    "name":  "str",
    "email": "str",
    "age":   "int"
})
print("Table created")

# 3. Insert
flash.add("users", {"name": "Alice", "email": "alice@mail.com", "age": 25})
flash.add("users", {"name": "Bob",   "email": "bob@mail.com",   "age": 17})
flash.bulk_insert("users", [
    {"name": "Carol", "email": "carol@mail.com", "age": 30},
    {"name": "Dave",  "email": "dave@mail.com",  "age": 22},
])
print("Inserted 4 records")

# 4. Read all
print("\nAll users:")
for u in flash.all("users"):
    print(" ", u)

# 5. Filter
print("\nAge > 18:")
for u in flash.where("users", {"age": {">": 18}}):
    print(" ", u)

# 6. Select specific fields
print("\nNames only:")
for u in flash.select("users", fields=["name", "age"]):
    print(" ", u)

# 7. Count
print("\nTotal users:", flash.count("users"))
print("Adults:", flash.count("users", {"age": {">": 18}}))

# 8. Paginate
page = flash.paginate("users", page=1, size=2)
print("\nPage 1:", page)

# 9. Update
updated = flash.update("users", {"name": "Alice"}, {"age": 26})
print("\nUpdated rows:", updated)

# 10. Triggers
@flash.before_insert("users")
def check(data):
    print(f"  [trigger] Inserting: {data}")

@flash.after_insert("users")
def done(data, result):
    print(f"  [trigger] Done, ID: {result}")

flash.add("users", {"name": "Eve", "email": "eve@mail.com", "age": 28})

# 11. Delete
deleted = flash.delete("users", {"name": "Bob"})
print("\nDeleted:", deleted)

# 12. Truncate
# flash.truncate("users")   # uncomment to test

# 13. Drop
# flash.drop_table("users") # uncomment to test

flash.close()
print("\n All tests passed!")