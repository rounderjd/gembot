import os
print(f"POSTGRES_DB: {os.getenv('POSTGRES_DB')}")
print(f"POSTGRES_USER: {os.getenv('POSTGRES_USER')}")
print(f"POSTGRES_PASSWORD: {os.getenv('POSTGRES_PASSWORD')}")
print(f"POSTGRES_HOST: {os.getenv('POSTGRES_HOST')}")
print(f"POSTGRES_PORT: {os.getenv('POSTGRES_PORT')}")