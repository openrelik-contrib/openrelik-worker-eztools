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
from .utils import _run_ez_tool

# --- AppCompatCacheParser Task ---
ACC_TASK_NAME = "openrelik-worker-eztools.tasks.appcompatcacheparser"
ACC_TASK_METADATA = {
    "display_name": "EZTool: AppCompatCacheParser",
    "description": "Runs AppCompatCacheParser.exe from Eric Zimmermann's EZTools to parse AppCompatCache data from SYSTEM hive files. Captures standard output.",
    "task_config": [
        {
            "name": "output_format",
            "label": "Output Format",
            "description": "Select the output format. 'stdout' captures console output. Other options use AppCompatCacheParser's direct file generation (e.g., --csv).",
            "type": "select",
            "items": [  # Changed from 'options' to 'items' and using list of strings
                "stdout",
                "csvf",
                "csv",
            ],
            "default": "stdout",
            "required": True,
        },
    ],
}

# Tool-specific configuration for output formats
ACC_OUTPUT_FORMAT_CONFIG = {
    "csv": {  # For the tool's --csv <directory> flag
        "flag": "--csv",
        "pattern": "AppCompatCacheParser_Output_*.csv",  # Tool creates this file inside the directory
        "output_target_type": "directory",
    },
    "csvf": {  # For the tool's --csvf <filepath> flag
        "flag": "--csvf",
        # Pattern should match the filename worker constructs and passes to the tool.
        # Worker constructs filename like: {input_base}_{tool_display_name}.{selected_format}
        # e.g., myinput_AppCompatCacheParser.exe.csvf
        "pattern": "*_AppCompatCacheParser.exe.csvf",
        "output_target_type": "directory_with_filename",
    },
}


@celery.task(bind=True, name=ACC_TASK_NAME, metadata=ACC_TASK_METADATA)
def appcompatcacheparser_command(
    self,
    pipe_result: str = None,
    input_files: list = None,
    output_path: str = None,
    workflow_id: str = None,
    task_config: dict = None,
) -> str:
    """Run AppCompatCacheParser.exe on input SYSTEM hive files."""
    effective_task_config = task_config if task_config is not None else {}

    # Absolute path to the dotnet executable
    dotnet_executable_path = os.path.expanduser("/usr/bin/dotnet")
    # Assuming AppCompatCacheParser.dll will be built and placed here, similar to other EZTools
    appcompatcacheparser_dll_path = (
        "/opt/AppCompatCacheParser_built_from_source/AppCompatCacheParser.dll"
    )

    executable_list_for_acc = [
        dotnet_executable_path,
        appcompatcacheparser_dll_path,
    ]

    return _run_ez_tool(
        executable_command_list=executable_list_for_acc,
        tool_display_name="AppCompatCacheParser.exe",
        tool_file_argument_flag="-f",  # AppCompatCacheParser uses -f for files
        tool_specific_args_key="appcompatcacheparser_arguments",
        tool_output_format_config=ACC_OUTPUT_FORMAT_CONFIG,
        pipe_result=pipe_result,
        input_files=input_files,
        output_path=output_path,
        workflow_id=workflow_id,
        task_config=effective_task_config,
    )
