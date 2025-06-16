import os  # For os.path.exists and os.access

from .app import celery
from .utils import _run_ez_tool  # Import from the new utils.py

# --- LECmd Task ---
LECMD_TASK_NAME = "openrelik-worker-eztools.tasks.lecmd"
LECMD_TASK_METADATA = {
    "display_name": "EZTool: LECmd (LNK File Parser)",
    "description": "Runs LECmd.exe from Eric Zimmermann's EZTools to parse LNK files. (only output format csv or json supported)",
    # by the user will be available to the task function when executing (task_config).
    "task_config": [
        {
            "name": "output_format",
            "label": "Output Format",
            "description": "Select the output format. 'stdout' captures console output. Other options use LECmd's direct file generation (e.g., --csv).",
            "type": "select",
            "items": [
                "stdout",
                "csv",
                "json",
            ],
            "default": "stdout",
            "required": True,
        },
    ],
}

# Tool-specific configuration for output formats
LECMD_OUTPUT_FORMAT_CONFIG = {
    "csv": {
        "flag": "--csv",
        # LECmd --csv expects a directory and creates a file like YYYYMMDDHHMMSS_LECmd_Output.csv inside it.
        "pattern": "*_LECmd_Output.csv",
        "output_target_type": "directory",
    },
    "json": {
        "flag": "--json",
        # Based on observed behavior and similarity to --csv, assume --json also expects a directory
        # and creates a file inside it. Guessing the pattern.
        "pattern": "*_LECmd_Output.json",
        "output_target_type": "directory",
    },
}


@celery.task(bind=True, name=LECMD_TASK_NAME, metadata=LECMD_TASK_METADATA)
def lecmd_command(
    self,
    pipe_result: str = None,
    input_files: list = None,
    output_path: str = None,
    workflow_id: str = None,
    task_config: dict = None,
) -> str:
    """Run LECmd on input LNK files.

    Args:
        pipe_result: Base64-encoded result from the previous Celery task, if any.
        input_files: List of input file dictionaries (unused if pipe_result exists).
        output_path: Path to the output directory.
        workflow_id: ID of the current workflow.
        task_config: User configuration for the task.

    Returns:
        Base64-encoded dictionary containing task results.
    """
    # Ensure task_config is not None, providing an empty dict if it is,
    # as _run_ez_tool expects it.
    # The OpenReliK core should always provide this, but defensive coding is good.
    effective_task_config = task_config if task_config is not None else {}

    # Path to the dotnet executable (installed via dotnet-install.sh, typically in ~/.dotnet/dotnet)
    dotnet_executable_path = os.path.expanduser("/usr/bin/dotnet")
    # Path to the LECmd.dll built from source
    lecmd_dll_path = "/opt/LECmd_built_from_source/LECmd.dll"

    # Form the command list for executing: dotnet /path/to/LECmd.dll
    executable_list_for_lecmd = [
        dotnet_executable_path,
        lecmd_dll_path,
    ]

    return _run_ez_tool(
        executable_command_list=executable_list_for_lecmd,
        tool_display_name="LECmd.exe",  # For display, logging, and output file naming
        tool_file_argument_flag="-f",  # LECmd uses -f for files
        tool_specific_args_key="lecmd_arguments",
        tool_output_format_config=LECMD_OUTPUT_FORMAT_CONFIG,
        pipe_result=pipe_result,
        input_files=input_files,
        output_path=output_path,
        workflow_id=workflow_id,
        task_config=effective_task_config,
    )
