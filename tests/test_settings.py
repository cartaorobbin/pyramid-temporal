"""Unit tests for pyramid_temporal connection settings (no server required)."""

import asyncio

import pytest
from pyramid.config import Configurator


@pytest.mark.parametrize(
    "extra_settings, expected",
    [
        ({}, "default"),
        ({"pyramid_temporal.temporal_namespace": "my-namespace"}, "my-namespace"),
    ],
    ids=["default", "override"],
)
def test_temporal_namespace_setting(extra_settings, expected):
    """The namespace setting defaults to 'default' and honors an explicit override."""
    config = Configurator(settings={"pyramid_temporal.auto_connect": "false", **extra_settings})
    config.include("pyramid_temporal")

    assert config.get_settings()["pyramid_temporal.temporal_namespace"] == expected


def test_task_queue_defaults_to_default():
    """task_queue defaults to 'default' when not set in the application settings."""
    config = Configurator(settings={"pyramid_temporal.auto_connect": "false"})
    config.include("pyramid_temporal")

    assert config.get_settings()["pyramid_temporal.task_queue"] == "default"


def test_setup_defers_client_when_event_loop_running():
    """When included inside a running loop, the client is deferred (registered as None).

    No server is required: the connection is skipped precisely because a loop is
    already running, so the host value is irrelevant here.
    """

    async def include_within_running_loop():
        config = Configurator(
            settings={
                "pyramid_temporal.auto_connect": "true",
                "pyramid_temporal.temporal_host": "unused:7233",
            }
        )
        config.include("pyramid_temporal")
        return config.registry["temporal_client"]

    assert asyncio.run(include_within_running_loop()) is None
