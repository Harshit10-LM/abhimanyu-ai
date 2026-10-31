"""Project structure indexer and dynamic prompt factory.

Inspired by Cyréna. Detects project frameworks (Arduino Sketch, PlatformIO, ESP-IDF)
and provides focused, task-specific prompts to local models instead of monolithic prompts.
"""

from dataclasses import dataclass
import os
import re
from typing import Dict, List, Optional


@dataclass
class ProjectManifest:
    """Structure and metadata of an embedded project."""

    framework: str  # "arduino", "platformio", "espidf", "single_sketch"
    entry_point_file: str
    source_files: List[str]
    config_files: List[str]
    libraries_used: List[str]


class ProjectContextManager:
    """Discovers project structure and generates focused, modular LLM prompts."""

    @staticmethod
    def detect_project_structure(root_dir: str) -> ProjectManifest:
        """Detects whether a directory is Arduino, PlatformIO, or ESP-IDF."""
        if not os.path.exists(root_dir):
            return ProjectManifest(
                framework="single_sketch",
                entry_point_file="sketch.ino",
                source_files=["sketch.ino"],
                config_files=[],
                libraries_used=[],
            )

        files = os.listdir(root_dir)

        # PlatformIO
        if "platformio.ini" in files:
            src_files = []
            src_dir = os.path.join(root_dir, "src")
            if os.path.exists(src_dir):
                src_files = [os.path.join("src", f) for f in os.listdir(src_dir) if f.endswith((".cpp", ".c", ".h"))]
            return ProjectManifest(
                framework="platformio",
                entry_point_file="src/main.cpp",
                source_files=src_files,
                config_files=["platformio.ini"],
                libraries_used=[],
            )

        # ESP-IDF
        if "CMakeLists.txt" in files and ("main" in files or "sdkconfig" in files):
            return ProjectManifest(
                framework="espidf",
                entry_point_file="main/main.c",
                source_files=["main/main.c"],
                config_files=["CMakeLists.txt"],
                libraries_used=[],
            )

        # Standard Arduino Sketch
        ino_files = [f for f in files if f.endswith(".ino")]
        if ino_files:
            return ProjectManifest(
                framework="arduino",
                entry_point_file=ino_files[0],
                source_files=ino_files,
                config_files=[],
                libraries_used=[],
            )

        return ProjectManifest(
            framework="single_sketch",
            entry_point_file="sketch.ino",
            source_files=["sketch.ino"],
            config_files=[],
            libraries_used=[],
        )

    @staticmethod
    def get_task_prompt(task_name: str, context: Dict[str, str]) -> str:
        """Generates a modular, task-specific prompt based on Cyréna dynamic prompt architecture."""
        if task_name == "audit":
            return (
                f"You are a firmware auditing engine. Analyze this {context.get('board_name', 'microcontroller')} "
                "code strictly for hardware configuration bugs, missing pinModes, and timing errors. "
                "Output must adhere strictly to JSON."
            )
        elif task_name == "optimize":
            return (
                "You are an embedded performance engineer. Convert blocking delay() routines into non-blocking "
                "millis() state machines while preserving timing intent. Explain the transformation."
            )
        elif task_name == "serial":
            return (
                "You are an embedded serial diagnostics expert. Analyze the provided serial monitor log. "
                "Distinguish direct observed log facts from engineering hypotheses. Recommend multimeter checks."
            )
        elif task_name == "wiring":
            return (
                "You are a hardware electronics specialist. Generate a pin-to-component wiring table with "
                "MCU Pin, Component, Component Pin, and Purpose."
            )
        return "You are an embedded engineering assistant."

