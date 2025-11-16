import asyncio
import sys
from monitor import OpenAIStatusMonitor


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="OpenAI Status Page Monitor")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run once and exit (for testing)"
    )

    args = parser.parse_args()

    async with OpenAIStatusMonitor(poll_interval=args.interval) as monitor:
        if args.test:
            print("Testing mode - running once...")
            await monitor.check_status_updates()
        else:
            await monitor.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
