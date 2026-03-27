import os


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"Sunrise worker scaffold ready. Redis endpoint: {redis_url}")


if __name__ == "__main__":
    main()
