"""Basic smoke test verifying package structure and dependencies."""

def test_imports():
    import boto3
    import pydantic
    import yaml
    import pytest
    import backend.src.core
    import backend.src.aws
    import backend.src.ai
    import backend.src.handlers

    assert pydantic.__version__.startswith("2.")
    assert int(boto3.__version__.split(".")[1]) >= 40
