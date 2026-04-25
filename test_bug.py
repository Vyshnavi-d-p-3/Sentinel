import subprocess

def run_command(user_input):
    result = subprocess.run(user_input, shell=True, capture_output=True)
    return result.stdout.decode()

def get_user(db, name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    return db.execute(query)
