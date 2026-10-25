import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

import config
from activities import calculate_ticket_energy, generate_ai_fix, log_transition
from workflows import BribeBoardWorkflow


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.info(
        f"Connecting worker to Temporal at {config.TEMPORAL_ADDRESS} (namespace: {config.TEMPORAL_NAMESPACE})..."
    )
    client = await Client.connect(
        config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE
    )
    worker = Worker(
        client,
        task_queue=config.TASK_QUEUE,
        workflows=[BribeBoardWorkflow],
        activities=[log_transition, generate_ai_fix, calculate_ticket_energy],
    )
    logging.info(
        f"Worker active! Listening on task queue '{config.TASK_QUEUE}'. "
        f"Registered workflows: {[BribeBoardWorkflow.__name__]}, "
        f"Registered activities: {[log_transition.__name__, generate_ai_fix.__name__, calculate_ticket_energy.__name__]}"
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
