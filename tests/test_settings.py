"""Unit tests for pyramid_temporal connection settings (no server required)."""

from pyramid.config import Configurator


def test_temporal_namespace_defaults_to_default():
    config = Configurator(settings={"pyramid_temporal.auto_connect": "false"})
    config.include("pyramid_temporal")

    assert config.get_settings()["pyramid_temporal.temporal_namespace"] == "default"


def test_temporal_namespace_can_be_overridden():
    config = Configurator(
        settings={
            "pyramid_temporal.auto_connect": "false",
            "pyramid_temporal.temporal_namespace": "my-namespace",
        }
    )
    config.include("pyramid_temporal")

    assert config.get_settings()["pyramid_temporal.temporal_namespace"] == "my-namespace"
