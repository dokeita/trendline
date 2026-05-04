#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.trendline_stack import TrendlineStack

app = cdk.App()
TrendlineStack(app, "TrendlineStack")
app.synth()
