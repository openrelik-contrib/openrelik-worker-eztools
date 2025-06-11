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

import subprocess
import os
import tempfile
import shutil
from pathlib import Path

# pylint: disable=g-multiple-import
from typing import List, Dict, Optional, Tuple

from openrelik_worker_common.file_utils import create_output_file
from openrelik_worker_common.task_utils import create_task_result, get_input_files


def _build_reporting_command_string(
    tool_display_name: str,
    tool_file_argument_flag: str,
    user_provided_args_str: str,
    selected_output_format: str,
    tool_output_format_config: Optional[Dict],
) -> str:
    """Builds a string representation of the command for reporting purposes.

    This string is used in the task result metadata to show the user
    the command that was conceptually executed, abstracting away temporary
    paths managed by the worker.

    Args:
        tool_display_name: The name of the tool for display (e.g., "LECmd.exe").
        tool_file_argument_flag: The flag used by the tool for the input file (e.g., "-f").
        user_provided_args_str: A string of arguments provided by the user.
        selected_output_format: The output format selected by the user (e.g., "csv", "stdout").
        tool_output_format_config: Configuration dictionary for tool output formats.

    Returns:
        A string representing the command executed, suitable for reporting.
    """
    reporting_command_string = (
        f"{tool_display_name} {tool_file_argument_flag} <input_file_path>"
    )
    if user_provided_args_str:
        reporting_command_string += f" {user_provided_args_str}"
    if (
        tool_output_format_config
        and selected_output_format != "stdout"
        and selected_output_format in tool_output_format_config
    ):
        reporting_command_string += f" {tool_output_format_config[selected_output_format]['flag']} <worker_temp_dir_or_file>"
    return reporting_command_string


def _validate_input_file(
    input_file_path: Optional[str], input_file_display_name: str, tool_display_name: str
):
    """Validates that the input file exists and is readable by the worker.

    Args:
        input_file_path: The absolute path to the input file on the worker.
        input_file_display_name: The display name of the input file for logging/errors.
        tool_display_name: The name of the tool for logging/errors.

    Raises:
        ValueError: If the input_file_path is None or empty.
        FileNotFoundError: If the file does not exist at the given path.
        PermissionError: If the worker does not have read access to the file.
    """
    if not input_file_path:
        raise ValueError(
            f"Invalid or missing file path for input: {input_file_display_name} for {tool_display_name}"
        )
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(
            f"Input file for {tool_display_name} not found by worker at path: {input_file_path}"
        )
    if not os.access(input_file_path, os.R_OK):
        raise PermissionError(
            f"Input file for {tool_display_name} is not readable by worker at path: {input_file_path}"
        )
    print(
        f"File '{input_file_path}' exists and is readable by the worker for {tool_display_name}."
    )


def _prepare_tool_file_output_args(
    selected_output_format: str,
    tool_output_format_config: Optional[Dict],
    user_provided_args_list: List[str],
    input_file_path: str,
    tool_display_name: str,
) -> Tuple[Optional[str], List[str], Optional[str]]:
    """Prepares arguments and a temporary directory for tools that generate file output.

    This function determines the output destination argument to pass to the tool
    based on the selected output format and its configuration (`output_target_type`).
    It also creates a temporary directory if needed and identifies the pattern
    to look for the generated output file(s).

    Args:
        selected_output_format: The output format selected by the user (e.g., "csv").
        tool_output_format_config: Configuration dictionary for tool output formats.
        user_provided_args_list: A list of arguments provided by the user.
        input_file_path: The absolute path to the input file being processed.
        tool_display_name: The name of the tool for display and naming temporary files.

    Returns:
        A tuple containing:
        - temp_dir: The path to the created temporary directory, or None if stdout is selected.
        - cmd_args_for_tool: A list of command-line arguments to append for the tool's output destination.
        - output_pattern: The glob pattern to find the output file(s) in the temp directory, or None.
    """
    if (
        selected_output_format == "stdout"
        or not tool_output_format_config
        or selected_output_format not in tool_output_format_config
    ):
        return None, [], None  # No temp dir, no extra args, no pattern needed

    format_details = tool_output_format_config[selected_output_format]
    format_flag = format_details["flag"]
    output_pattern = format_details["pattern"]
    output_target_type = format_details.get("output_target_type", "file")

    if format_flag in user_provided_args_list:
        print(
            f"Warning: User provided '{format_flag}' in arguments while also selecting "
            f"'{selected_output_format}' format. The worker will manage the '{format_flag}' "
            f"argument. Please remove it from custom arguments if this was unintentional."
        )

    temp_dir = tempfile.mkdtemp(prefix=f"eztool_{selected_output_format}_")
    cmd_args_for_tool = []
    tool_output_destination_arg = ""

    if output_target_type == "directory":
        tool_output_destination_arg = temp_dir
    elif (
        output_target_type == "file" or output_target_type == "directory_with_filename"
    ):
        base_input_filename = Path(input_file_path).stem
        temp_output_filename = (
            f"{base_input_filename}_{tool_display_name}.{selected_output_format}"
        )
        full_temp_output_path = Path(temp_dir) / temp_output_filename
        tool_output_destination_arg = str(full_temp_output_path)
    else:  # Fallback for unknown or misconfigured output_target_type
        print(
            f"Warning: Unknown output_target_type '{output_target_type}' for format '{selected_output_format}'. Defaulting to constructing a file path argument."
        )
        base_input_filename = Path(input_file_path).stem
        temp_output_filename = (
            f"{base_input_filename}_{tool_display_name}.{selected_output_format}"
        )
        full_temp_output_path = Path(temp_dir) / temp_output_filename
        tool_output_destination_arg = str(full_temp_output_path)

    cmd_args_for_tool.extend([format_flag, tool_output_destination_arg])
    return temp_dir, cmd_args_for_tool, output_pattern


def _process_single_input_file(
    input_file_details: Dict,
    executable_command_list: List[str],
    tool_display_name: str,
    tool_file_argument_flag: str,
    user_provided_args_list: List[str],
    selected_output_format: str,
    tool_output_format_config: Optional[Dict],
    worker_output_path: str,
    worker_output_extension: str,
    worker_output_data_type: str,
) -> Dict:
    """Processes a single input file with the specified EZTool.

    This function handles validation, command construction, execution,
    output capture/processing, and error handling for one input file.

    Args:
        input_file_details: Dictionary containing 'path' and 'display_name' for the input file.
        executable_command_list: Base command list for the tool.
        tool_display_name: Display name of the tool.
        tool_file_argument_flag: Command-line flag for the input file.
        user_provided_args_list: List of user-provided arguments.
        selected_output_format: The chosen output format (e.g., "stdout", "csv").
        tool_output_format_config: Configuration for tool-specific output formats.
        worker_output_path: Base path for worker output files.
        worker_output_extension: Extension for the final output file.
        worker_output_data_type: Data type for the final output file.

    Returns:
        A dictionary representing the output file object, to be included in task results.

    Raises:
        FileNotFoundError: If the executable or DLL is not found during subprocess run.
                           (Input file not found is handled by _validate_input_file).
    """
    input_file_path = input_file_details.get("path")
    input_file_display_name = input_file_details.get("display_name", "unknown_file")

    _validate_input_file(input_file_path, input_file_display_name, tool_display_name)
    input_file_path_str = str(input_file_path)  # Guaranteed to be a string now

    output_file_obj = create_output_file(
        worker_output_path,
        display_name=f"{tool_display_name}_output_for_{input_file_display_name}",
        extension=worker_output_extension,
        data_type=worker_output_data_type,
    )

    temp_dir_for_tool_output = None
    output_content = b""

    print(f"Processing file for {tool_display_name}: '{input_file_path_str}'")
    try:
        current_command_to_run = list(executable_command_list)
        current_command_to_run.extend([tool_file_argument_flag, input_file_path_str])
        current_command_to_run.extend(user_provided_args_list)

        (
            temp_dir_for_tool_output,
            cmd_args_for_tool_file_output,
            tool_output_pattern,
        ) = _prepare_tool_file_output_args(
            selected_output_format,
            tool_output_format_config,
            user_provided_args_list,
            input_file_path_str,
            tool_display_name,
        )
        current_command_to_run.extend(cmd_args_for_tool_file_output)

        command_str_for_logging = " ".join(current_command_to_run)
        print(f"Executing command for {tool_display_name}: {command_str_for_logging}")

        process = subprocess.run(
            current_command_to_run, capture_output=True, text=False, check=False
        )

        captured_stdout_for_log = (
            process.stdout.decode(errors="ignore") if process.stdout else ""
        )
        captured_stderr = (
            process.stderr.decode(errors="ignore") if process.stderr else ""
        )

        if captured_stdout_for_log:
            print(
                f"Tool {tool_display_name} stdout for {input_file_path_str}:\n{captured_stdout_for_log[:1000]}..."
            )
        if captured_stderr:
            print(
                f"Tool {tool_display_name} stderr for {input_file_path_str}:\n{captured_stderr[:1000]}..."
            )

        if (
            temp_dir_for_tool_output
            and tool_output_format_config
            and tool_output_pattern
        ):
            if process.returncode != 0:
                print(
                    f"Warning: {tool_display_name} exited with code {process.returncode} when attempting to generate '{selected_output_format}' file."
                )

            format_details = tool_output_format_config[selected_output_format]
            output_target_type = format_details.get("output_target_type", "file")
            glob_func = (
                Path(temp_dir_for_tool_output).rglob
                if output_target_type == "directory"
                else Path(temp_dir_for_tool_output).glob
            )

            all_matches = list(glob_func(tool_output_pattern))
            generated_files = [p for p in all_matches if p.is_file()]

            if not generated_files:
                error_message = (
                    f"Error: {tool_display_name} did not produce the expected '{selected_output_format}' file "
                    f"(pattern: '{tool_output_pattern}') in {temp_dir_for_tool_output}.\n"
                    f"Command: '{command_str_for_logging}'.\n"
                    f"Return code: {process.returncode}\nStdout: {captured_stdout_for_log}\nStderr: {captured_stderr}"
                )
                output_content = (
                    process.stderr if process.stderr else error_message.encode()
                )
                print(error_message)
            elif len(generated_files) > 1:
                generated_files.sort(key=os.path.getmtime, reverse=True)
                print(
                    f"Warning: Multiple files matched pattern '{tool_output_pattern}' and are files. Using the newest: {generated_files[0]}"
                )
                with open(generated_files[0], "rb") as f_in:
                    output_content = f_in.read()
            else:
                with open(generated_files[0], "rb") as f_in:
                    output_content = f_in.read()
        else:  # Capture stdout
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    current_command_to_run,
                    output=process.stdout,
                    stderr=process.stderr,
                )
            output_content = process.stdout

        with open(output_file_obj.path, "wb") as fh:
            fh.write(output_content)

    except subprocess.CalledProcessError as e:
        stdout_decoded = (
            e.stdout.decode(errors="ignore")
            if isinstance(e.stdout, bytes)
            else e.stdout
        )
        stderr_decoded = (
            e.stderr.decode(errors="ignore")
            if isinstance(e.stderr, bytes)
            else e.stderr
        )
        error_message = (
            f"Error running {tool_display_name} on {input_file_path_str}.\n"
            f"Command: '{' '.join(e.cmd)}'.\nReturn code: {e.returncode}\n"
            f"Stdout: {stdout_decoded}\nStderr: {stderr_decoded}"
        )
        with open(output_file_obj.path, "w", encoding="utf-8") as fh_err:
            fh_err.write(error_message)
        print(error_message)
    except FileNotFoundError as e:  # This is for dotnet or the DLL itself
        if e.filename in executable_command_list:
            raise FileNotFoundError(
                f"The command or DLL '{e.filename}' was not found. "
                "Ensure .NET is installed and DLL paths are correct."
            ) from e
        print(
            f"Unexpected FileNotFoundError for: {e.filename}"
        )  # Should be caught by _validate_input_file
        raise  # Re-raise if it's not the executable itself
    finally:
        if temp_dir_for_tool_output:
            print(f"Cleaning up temporary directory: {temp_dir_for_tool_output}")
            shutil.rmtree(temp_dir_for_tool_output, ignore_errors=True)

    return output_file_obj.to_dict()


def _run_ez_tool(
    executable_command_list: list,
    tool_display_name: str,  # e.g., "LECmd.dll" for logging and output file naming
    tool_file_argument_flag: str,  # e.g., "-f" for file or "-d" for directory
    tool_specific_args_key: str,
    tool_output_format_config: dict,  # New: e.g. {"csv": {"flag": "--csv", "pattern": "LECmd_*.csv"}}
    pipe_result: str,
    input_files: list,
    output_path: str,
    workflow_id: str,
    task_config: dict,
) -> str:
    """
    Helper function to run an EZTool, supporting both stdout capture and
    direct file output generation by the tool.

    This function orchestrates the execution of a command-line tool for each
    input file. It handles input file validation, command construction,
    execution via subprocess, capturing stdout/stderr, managing temporary
    directories for tool-generated file output, and writing the final output
    to the worker's designated output path.

    Args:
        executable_command_list: A list representing the base command to run the tool
                                 (e.g., `['dotnet', '/path/to/Tool.dll']`).
        tool_display_name: The name of the tool for display, logging, and output file naming.
        tool_file_argument_flag: The command-line flag the tool uses to specify the input file (e.g., "-f").
        tool_specific_args_key: The key in `task_config` where user-provided arguments for this tool are stored.
        tool_output_format_config: Configuration dictionary mapping output format names to their flags, patterns, and target types.
        pipe_result: Base64-encoded result from the previous Celery task, if any.
        input_files: List of input file dictionaries (used if pipe_result is None).
        output_path: The base path where the worker should save output files.
        workflow_id: The ID of the current workflow.
        task_config: A dictionary containing user configuration for the task.

    Returns:
        A base64-encoded string representing the task result dictionary,
        containing details about the generated output files.

    Raises:
        ValueError: If no input files are provided.
        FileNotFoundError: If the executable or DLL is not found.
        subprocess.CalledProcessError: If the tool exits with a non-zero status code
                                       when capturing stdout.
        RuntimeError: If the tool fails to produce the expected output file(s)
                      when configured for file output.
    """
    processed_input_files = get_input_files(pipe_result, input_files or [])
    if not processed_input_files:
        raise ValueError(f"No input files provided to {tool_display_name}.")

    final_output_files = []

    user_provided_args_str = (
        task_config.get(tool_specific_args_key, "") if tool_specific_args_key else ""
    )
    user_provided_args_list = (
        user_provided_args_str.split() if user_provided_args_str else []
    )
    selected_output_format = task_config.get("output_format", "stdout")
    output_data_type = task_config.get("output_data_type", "text_file")
    output_extension = (
        selected_output_format
        if selected_output_format != "stdout"
        else task_config.get("output_file_extension", "txt")
    )

    reporting_command_string = _build_reporting_command_string(
        tool_display_name,
        tool_file_argument_flag,
        user_provided_args_str,
        selected_output_format,
        tool_output_format_config,
    )

    for input_file in processed_input_files:
        try:
            output_file_dict = _process_single_input_file(
                input_file_details=input_file,
                executable_command_list=executable_command_list,
                tool_display_name=tool_display_name,
                tool_file_argument_flag=tool_file_argument_flag,
                user_provided_args_list=user_provided_args_list,
                selected_output_format=selected_output_format,
                tool_output_format_config=tool_output_format_config,
                worker_output_path=output_path,
                worker_output_extension=output_extension,
                worker_output_data_type=output_data_type,
            )
            final_output_files.append(output_file_dict)
        except (
            FileNotFoundError
        ):  # Raised by _process_single_input_file if executable not found
            # If the executable itself is not found, we should probably stop.
            raise
        except (
            Exception
        ) as e:  # Catch other unexpected errors from _process_single_input_file
            # Log and continue to next file if possible, or decide to re-raise
            print(f"Unexpected error processing file {input_file.get('path')}: {e}")
            # Potentially create an error entry for this file in final_output_files
            # For now, it will just skip adding to final_output_files if an error occurs
            # that isn't handled by writing to the output_file_obj within _process_single_input_file

    if (
        not final_output_files
    ):  # Should not happen if processed_input_files was not empty
        raise RuntimeError(f"No output files were generated by {tool_display_name}.")

    return create_task_result(
        output_files=final_output_files,
        workflow_id=workflow_id,
        command=reporting_command_string,
        meta={},
    )
