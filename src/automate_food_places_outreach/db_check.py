import os #gives access to env variables

import psycopg #imports postgreSQL driver


def main() -> None:
    with psycopg.connect( #opens db connection
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"], #raises key error if var is missing during set up
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor: #connection.cursor() creates object used to execute SQL and read results
            cursor.execute("SELECT current_database(), current_user;")
            database_name, user_name = cursor.fetchone()

    print(f"Connected to database {database_name!r} as user {user_name!r}.") #!r prints those values with quotes, making empty or unusual values easier to notice


if __name__ == "__main__":
    main()
    