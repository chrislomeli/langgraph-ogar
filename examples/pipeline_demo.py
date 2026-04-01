#!/usr/bin/env python3
"""
pipeline_demo.py — End-to-end pipeline: world → sensors → queue → bridge → agent

Demonstrates the full data flow:
  1. WorldEngine advances the simulation each tick.
  2. SensorPublisher ticks sensors that read from the engine.
  3. Sensors emit SensorEvents onto a SensorEventQueue.
  4. EventBridgeConsumer reads events and invokes cluster agent graphs.
  5. Cluster agent produces AnomalyFindings.

Run:
  python examples/pipeline_demo.py
"""

import asyncio
import logging
import random

from ogar.world.scenarios.wildfire_basic import create_basic_wildfire
from ogar.sensors.world_sensors import (
    TemperatureSensor,
    HumiditySensor,
    WindSensor,
    SmokeSensor,
)
from ogar.sensors.publisher import SensorPublisher
from ogar.transport.queue import SensorEventQueue
from ogar.bridge.consumer import EventBridgeConsumer
from ogar.agents.cluster.graph import build_cluster_agent_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline_demo")


CLUSTER_ID = "cluster-north"
NUM_TICKS = 15


def build_sensors(engine):
    """Create sensors attached to the engine, all in one cluster."""
    return [
        TemperatureSensor(
            source_id="temp-A1",
            cluster_id=CLUSTER_ID,
            engine=engine,
            grid_row=3, grid_col=3,
            noise_std=0.5,
        ),
        TemperatureSensor(
            source_id="temp-B2",
            cluster_id=CLUSTER_ID,
            engine=engine,
            grid_row=7, grid_col=2,
            noise_std=0.5,
        ),
        HumiditySensor(
            source_id="hum-A1",
            cluster_id=CLUSTER_ID,
            engine=engine,
            noise_std=0.5,
        ),
        WindSensor(
            source_id="wind-A1",
            cluster_id=CLUSTER_ID,
            engine=engine,
        ),
        SmokeSensor(
            source_id="smoke-A1",
            cluster_id=CLUSTER_ID,
            engine=engine,
            grid_row=5, grid_col=3,
            noise_std=1.0,
        ),
    ]


async def main():
    random.seed(42)

    # ── Build the world ──────────────────────────────────────────────
    engine = create_basic_wildfire()
    logger.info("World created: %dx%d grid, ignition at (7,2)", engine.grid.rows, engine.grid.cols)

    # ── Build sensors ────────────────────────────────────────────────
    sensors = build_sensors(engine)
    logger.info("Sensors: %s", [s.source_id for s in sensors])

    # ── Build transport ──────────────────────────────────────────────
    queue = SensorEventQueue(maxsize=200)

    # ── Build publisher (with engine wired in) ───────────────────────
    publisher = SensorPublisher(
        sensors=sensors,
        queue=queue,
        tick_interval_seconds=0.0,   # as fast as possible for demo
        engine=engine,
    )

    # ── Build agent graph ────────────────────────────────────────────
    cluster_graph = build_cluster_agent_graph()

    # ── Build bridge consumer ────────────────────────────────────────
    findings_log = []

    def on_finding(finding):
        findings_log.append(finding)
        logger.info(
            "  ⚡ FINDING: [%s] %s (confidence=%.2f)",
            finding["anomaly_type"],
            finding["summary"][:80],
            finding["confidence"],
        )

    consumer = EventBridgeConsumer(
        queue=queue,
        agent_graph=cluster_graph,
        on_finding=on_finding,
        batch_size=5,    # invoke agent every 5 events per cluster
    )

    # ── Run the pipeline ─────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Starting pipeline: %d ticks, batch_size=5", NUM_TICKS)
    logger.info("=" * 60)

    # Publisher runs first (produces events), then consumer processes them.
    await publisher.run(ticks=NUM_TICKS)
    logger.info(
        "Publisher done: %d ticks, %d events enqueued",
        publisher.ticks_completed,
        queue.total_enqueued,
    )

    # Consume all queued events.
    await consumer.run(max_events=queue.total_enqueued)

    # ── Summary ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Pipeline complete")
    logger.info("  Engine ticks:    %d", engine.current_tick)
    logger.info("  Events produced: %d", queue.total_enqueued)
    logger.info("  Events consumed: %d", consumer.events_consumed)
    logger.info("  Agent calls:     %d", consumer.invocations)
    logger.info("  Findings:        %d", len(findings_log))
    logger.info("=" * 60)

    # Print ground truth vs sensor readings.
    summary = engine.grid.summary()
    logger.info("Ground truth — %s", summary)

    for f in findings_log:
        logger.info(
            "  Finding: %s | sensors=%s | confidence=%.2f",
            f["anomaly_type"],
            f["affected_sensors"],
            f["confidence"],
        )


if __name__ == "__main__":
    asyncio.run(main())
