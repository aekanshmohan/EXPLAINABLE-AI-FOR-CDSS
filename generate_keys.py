import bcrypt

passwords = ['radiology2026', 'cardio2026']

for pwd in passwords:
    hashed = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"Password '{pwd}' -> {hashed}")