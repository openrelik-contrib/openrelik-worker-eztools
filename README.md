# Openrelik worker eztools

The **OpenRelik EZTools Worker** is a Celery-based task processor designed to execute various command-line forensic tools from Eric Zimmerman's EZTools suite. This worker allows you to run selected command-line tools from Eric Zimmermann's EZTools suite (e.g., `LECmd`, `RBCmd`, `AppCompatCacheParser`) on input files. It captures the standard output of these tools and makes it available for further processing or storage within the OpenRelik platform.

Currently, this worker supports the following EZTools:

* **LECmd (LNK File Parser):** Parses LNK shortcut files and related artifacts.
* **RBCmd (Recycle Bin Command Line):** Parses `$I` and `$R` files from the Windows Recycle Bin.
* **AppCompatCacheParser:** Parses AppCompatCache (ShimCache) data from SYSTEM registry hives.


For each input file, the selected EZTool is executed. The worker captures the standard output (STDOUT) of the tool and saves it to an output file 
(e.g., `original_filename_lecmd.txt`). If an error occurs during processing, the task will reflect this.


## Deploy

Add the below configuration to the OpenRelik `docker-compose.yml` file.

```
openrelik-worker-eztools:
    container_name: openrelik-worker-eztools
    image: ghcr.io/openrelik/openrelik-worker-eztools:latest
    restart: always
    environment:
      - REDIS_URL=redis://openrelik-redis:6379
      - OPENRELIK_PYDEBUG=0
    volumes:
      - ./data:/usr/share/openrelik/data
    command: "celery --app=src.app worker --task-events --concurrency=4 --loglevel=INFO -Q openrelik-worker-eztools"
    # ports:
      # - 5678:5678 # For debugging purposes.
```

## Configuration

This worker provides task-specific configurations through the OpenRelik UI when dispatching a task. For each supported EZTool (e.g., LECmd, RBCmd), you can typically configure:

* **Tool-Specific Arguments:** Additional command-line arguments to pass to the selected EZTool (e.g., --csv C:\temp\out for LECmd). The input file path will be appended automatically by the worker.
        Note: This worker is designed to capture the standard output of the tools. Ensure any arguments provided are compatible with this behavior (i.e., the tool should print its primary output to STDOUT).

TODO: figure out the output format
* **Output File Extension:** The desired file extension for the output file that will store the captured STDOUT (e.g., txt, csv, json).
* **Output Data Type (Optional):** A specific data type string for OpenReLiK's internal metadata tracking (e.g., `lnk_file_analysis`, `recycle_bin_parsed`).

## Code Coverage

![Code Coverage](coverage.svg)

## Credit

Credit for the content of the worker goes to Eric Zimmerman

Download Eric Zimmerman's Tools
All of Eric Zimmerman's tools can be downloaded here: https://ericzimmerman.github.io/#!index.md.


## Test
```
pip install poetry
poetry install --with test --no-root
poetry run pytest --cov=. -v
```