"""
CLI entrypoint for the ChannelTalk auto-labeling pipeline.

Example:
    python -m channel_agent.runner --from 2024-08-01T00:00:00Z --to 2024-08-07T23:59:59Z
"""

import argparse
import logging
import sys

from .agent import ChannelAgent
from .channel_api import ChannelTalkClient
from .config import ChannelTalkConfig, OpenAIConfig, PipelineConfig
from .pipeline import ChannelLabelingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChannelTalk auto-labeling pipeline")
    parser.add_argument(
        "--from",
        dest="created_from",
        required=True,
        help="ISO8601 datetime inclusive start (e.g., 2024-08-01T00:00:00Z)",
    )
    parser.add_argument(
        "--to",
        dest="created_to",
        required=True,
        help="ISO8601 datetime inclusive end (e.g., 2024-08-07T23:59:59Z)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    channel_client = ChannelTalkClient(ChannelTalkConfig())
    agent = ChannelAgent(OpenAIConfig(), channel_client)
    pipeline = ChannelLabelingPipeline(channel_client, agent, PipelineConfig())

    output_path = pipeline.run(args.created_from, args.created_to)
    logging.info("Pipeline finished. Output: %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

