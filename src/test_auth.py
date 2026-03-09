from dotenv import load_dotenv
from kraken_client import from_env


def main() -> None:
    load_dotenv()
    client = from_env()
    resp = client.private_post("Balance")
    print(resp)


if __name__ == "__main__":
    main()
