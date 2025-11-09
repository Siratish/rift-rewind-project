#!/usr/bin/env python3
"""
AWS CDK App Entry Point for Rift Trivia Backend
"""
import os
from aws_cdk import App, Environment
from stacks.rift_trivia_stack import RiftTriviaStack

app = App()

# Get environment from context or use AWS CDK defaults
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION")

env = Environment(account=account, region=region)

# Create the main stack
RiftTriviaStack(
    app,
    "RiftTriviaStack",
    env=env,
    description="Rift Trivia serverless backend infrastructure",
)

app.synth()
