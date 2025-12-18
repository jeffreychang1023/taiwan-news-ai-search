"""
Iteration logger for saving detailed reasoning process to disk for debugging.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from misc.logger.logging_config_helper import get_configured_logger


logger = get_configured_logger("reasoning.iteration_logger")


def get_project_root_iterations_path() -> Path:
    """
    Get absolute path to reasoning iterations directory from project root.

    This ensures consistent directory location regardless of working directory.

    Returns:
        Absolute Path to data/reasoning/iterations/ from project root
    """
    # Get path to this file (reasoning/utils/iteration_logger.py)
    current_file = Path(__file__).resolve()
    # Navigate up to project root: iteration_logger.py -> utils/ -> reasoning/ -> python/ -> code/ -> NLWeb/
    project_root = current_file.parent.parent.parent.parent.parent
    # Build absolute path to iterations directory
    iterations_path = project_root / "data" / "reasoning" / "iterations"
    return iterations_path


class IterationLogger:
    """
    Logger for saving reasoning iteration data to disk for debugging.

    Saves detailed JSON logs per iteration for each agent's input/output,
    plus a session summary for the entire reasoning process.
    """

    def __init__(self, query_id: str):
        """
        Initialize iteration logger for a specific query.

        Args:
            query_id: Unique query identifier (used as directory name)
        """
        self.query_id = query_id
        self.logger = get_configured_logger(f"reasoning.iteration_logger.{query_id}")

        # Get base iterations directory
        base_path = get_project_root_iterations_path()

        # Create query-specific directory
        self.query_dir = base_path / query_id
        self.query_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Initialized iteration logger: {self.query_dir}")

    def log_agent_output(
        self,
        iteration: int,
        agent_name: str,
        input_prompt: str,
        output_response: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log agent input/output for a specific iteration.

        Args:
            iteration: Iteration number (1-based)
            agent_name: Name of agent (analyst, critic, writer)
            input_prompt: Prompt sent to agent
            output_response: Response received from agent
            metadata: Optional metadata (e.g., timing, model used)
        """
        filename = f"iteration_{iteration}_{agent_name}.json"
        filepath = self.query_dir / filename

        # Convert Pydantic models to dict for JSON serialization
        from pydantic import BaseModel
        if isinstance(output_response, BaseModel):
            output_response = output_response.model_dump()

        log_data = {
            "query_id": self.query_id,
            "iteration": iteration,
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "input_prompt": input_prompt,
            "output_response": output_response,
            "metadata": metadata or {}
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Logged {agent_name} output: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to log agent output: {e}")

    def log_summary(
        self,
        total_iterations: int,
        final_status: str,
        mode: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log session summary for the entire reasoning process.

        Args:
            total_iterations: Total number of iterations completed
            final_status: Final status (PASS, WARN, MAX_ITERATIONS, ERROR)
            mode: Research mode used (strict, discovery, monitor)
            metadata: Optional metadata (e.g., timing, sources analyzed)
        """
        filename = "session_summary.json"
        filepath = self.query_dir / filename

        summary_data = {
            "query_id": self.query_id,
            "total_iterations": total_iterations,
            "final_status": final_status,
            "mode": mode,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Logged session summary: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to log session summary: {e}")
