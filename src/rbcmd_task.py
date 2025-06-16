# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from .app import celery
from .utils import _run_ez_tool  # Import from the new utils.py

# Task name used to register and route the task to the correct queue.
RBCMD_TASK_NAME = "openrelik-worker-eztools.tasks.rbcmd"

# Task metadata for registration in the core system.
RBCMD_TASK_METADATA = {
    "display_name": "EZTool: RBCmd (Recycle Bin Parser)",
    "description": "Runs RBCmd.exe from Eric Zimmermann's EZTools to parse Recycle Bin artifacts. Captures standard output.",
    "task_config": [
        {
            "name": "output_format",
            "label": "Output Format",
            "description": "Select the output format. 'stdout' captures console output. Other options use RBCmd's direct file generation (e.g., --csv).",
            "type": "select",
            "items": [
                "stdout",
                "csv",
            ],
            "default": "stdout",
            "required": True,
        },
    ],
}

# Tool-specific configuration for output formats
RBCMD_OUTPUT_FORMAT_CONFIG = {
    "csv": {
        "flag": "--csv",
        "pattern": "*_RBCmd_Output.csv",  # Pattern to match RBCmd's default output filename
        "output_target_type": "directory",  # RBCmd --csv expects a directory
    },
}


@celery.task(bind=True, name=RBCMD_TASK_NAME, metadata=RBCMD_TASK_METADATA)
def rbcmd_command(
    self,
    pipe_result: str = None,
    input_files: list = None,
    output_path: str = None,
    workflow_id: str = None,
    task_config: dict = None,
) -> str:
    """Run RBCmd.exe on input Recycle Bin artifacts or directories."""
    effective_task_config = task_config if task_config is not None else {}

    dotnet_executable_path = os.path.expanduser("/usr/bin/dotnet")
    rbcmd_dll_path = "/opt/RBCmd_built_from_source/RBCmd.dll"
    executable_list_for_rbcmd = [dotnet_executable_path, rbcmd_dll_path]

    return _run_ez_tool(
        executable_command_list=executable_list_for_rbcmd,
        tool_display_name="RBCmd.exe",
        tool_file_argument_flag="-f",
        tool_specific_args_key=None,  # Explicitly no custom arguments from UI for this task
        tool_output_format_config=RBCMD_OUTPUT_FORMAT_CONFIG,
        pipe_result=pipe_result,
        input_files=input_files,
        output_path=output_path,
        workflow_id=workflow_id,
        task_config=effective_task_config,
    )
