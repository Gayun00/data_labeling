"""
ChannelTalk auto-labeling pipeline powered by OpenAI Agents.

This package stays isolated from the existing Excel-driven flow and
implements the design described in channel.md: ChannelTalk API fetchers,
PII masking, agent setup, and an end-to-end orchestration pipeline.
"""

from .agent import ChannelAgent
from .channel_api import ChannelTalkClient
from .pipeline import ChannelLabelingPipeline

__all__ = ["ChannelAgent", "ChannelTalkClient", "ChannelLabelingPipeline"]
