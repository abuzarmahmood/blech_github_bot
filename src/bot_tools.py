"""
Tools for the agents to use.
"""

import os
import sys

src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(src_dir)

# Keep everything but tool calls


def is_tool_related(
        x: dict,) -> bool:
    if 'tool_calls' in x.keys() or x['role'] == 'tool':
        return True


def get_local_repo_path(repo_name: str) -> str:
    """
    Get the path to the local repository

    Args:
        - repo_name : Name of repository (owner/repo)
            - Example: "openai/autogen"

    Returns:
        - Path to the local repository
    """
    repo_name_split = repo_name.split('/')
    repo_path = os.path.join(
        src_dir, 'repos', repo_name_split[0], repo_name_split[1])
    if os.path.exists(repo_path):
        return repo_path
    else:
        return f"Repository {repo_name} not found @ {repo_path}"


def get_tracked_repos() -> str:
    """
    Get the tracked repositories

    Returns:
        - List of tracked repositories
    """
    tracked_repos_path = os.path.join(base_dir, 'config', 'repos.txt')
    with open(tracked_repos_path, 'r') as file:
        tracked_repos = file.readlines()
    tracked_repos = [repo.strip() for repo in tracked_repos]
    return tracked_repos


def search_for_pattern(
        search_dir: str,
        pattern: str,
) -> str:
    """
    Search for a pattern in a directory.
    Can only search for python files.

    Inputs:
        - search_dir : Directory to search
        - pattern : Pattern to search for

    Returns:
        - Path to files with pattern
    """
    run_str = f"grep -irl {pattern} {search_dir} --include='*.py'"
    print(run_str)
    # out = os.system(run_str)
    out = os.popen(run_str).read()
    return out


def search_and_replace(
        file_path: str,
        search_text: str,
        replace_text: str,
) -> bool:
    """
    Search and replace text in a file

    Inputs:
        - file_path : Path to file
        - search_text : Text to search for
        - replace_text : Text to replace with

    Returns:
        - True if successful, False if search_text not found
    """
    # make backup
    import shutil
    import ast

    shutil.copy2(file_path, file_path + '.bak')

    with open(file_path, 'r') as file:
        file_data = file.read()

    # Check for exact match
    if search_text not in file_data:
        print(f"Search text not found in file: {file_path}")
        return False

    new_data = file_data.replace(search_text, replace_text)

    with open(file_path, 'w') as file:
        file.write(new_data)

    # Check that file is valid
    try:
        ast.parse(new_data)
    except SyntaxError as e:
        print('Editing file created a syntax error')
        print(f"Syntax error in file: {file_path}")
        print(e)
        # Restore backup
        shutil.copy2(file_path + '.bak', file_path)
        os.remove(file_path + '.bak')
        return False

    print('Search and replace successful')
    return True


def modify_lines(
        file_path: str,
        start_line: int,
        end_line: int,
        new_lines: str,
) -> bool:
    """
    Modify lines in a file
    Don't use escape characters

    - Can delete lines by setting new_lines to empty string
    - Can add lines by setting start_line = end_line
    - Can modify lines by setting start_line != end_line

    Inputs:
        - file_path : Path to file
        - start_line : Start line
        - end_line : End line (inclusive)
        - new_lines : New lines to replace with

    Returns:
        - True if successful, False otherwise
    """

    assert start_line <= end_line, "Start line must be less than or equal to end line"

    # make backup
    import shutil
    import ast

    shutil.copy2(file_path, file_path + '.bak')

    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Check for exact match
    if len(lines) < end_line:
        print(f"End line greater than number of lines in file: {file_path}")
        return False

    init_lines = lines[:start_line]
    end_lines = lines[end_line+1:]
    mod_lines = new_lines.split('\n')
    mod_lines = [line + '\n' for line in mod_lines]

    lines = init_lines + mod_lines + end_lines

    with open(file_path, 'w') as file:
        # file.write("".join(lines))
        file.writelines(lines)

    # Check that file is valid
    try:
        ast.parse("".join(lines))
    except SyntaxError as e:
        print('Editing file created a syntax error')
        print('View around modified lines')
        print_start = max(0, start_line - 5)
        print_end = min(start_line + len(mod_lines) + 5, len(lines))
        print("".join(f"{i:03}: {line}" for i,
              line in enumerate(lines[print_start:print_end])))
        print(f"Syntax error in file: {file_path}")
        print(e)
        # Restore backup
        shutil.copy2(file_path + '.bak', file_path)
        os.remove(file_path + '.bak')
        return False

    print('Modify lines successful')
    return True


def readlines(
        file_path: str,
        start_line: int,
        end_line: int,
) -> str:
    """
    Read lines from a file

    Inputs:
        - file_path : Path to file
        - start_line : Start line
        - end_line : End line

    Returns:
        - Lines from file
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()

    return "".join(lines[start_line:end_line])

# Tends to muddy the output too much
# def listdir(
#         directory : str,
#         extension : str = None,
#         ) -> str:
#     """List contents of a directory
#     Inputs:
#         - Directory : Path to directory
#         - Extension (optional) : Only return files with the given extension
#     """
#     if extension:
#         ext_str = f"-iname '*{extension}'"
#     else:
#         ext_str = ""
#     run_str = f"find {directory} " + ext_str
#     print(run_str)
#     # out = os.system(run_str)
#     out = os.popen(run_str).read()
#     return out


def search_for_file(
        directory: str,
        filename: str,
) -> str:
    """Search for a file in a directory
    Inputs:
        - Directory : Path to directory
        - Filename : Name of file

    Returns:
        - Path to file
    """
    run_str = f"find {directory} -iname '*{filename}*'"
    print(run_str)
    # out = os.system(run_str)
    out = os.popen(run_str).read()
    if out:
        return out
    else:
        return "File not found"


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in text by splitting on whitespace
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text.split())

def readfile(filepath: str, token_threshold: int = 1000) -> tuple[str, str | None]:
    """Read a file and return its contents with line numbers.
    Will return partial content if token threshold is exceeded.
    
    Args:
        filepath: Path to file to read
        token_threshold: Maximum number of tokens to return (default: 1000)
        
    Returns:
        Tuple of:
        - File contents with line numbers (may be truncated if exceeds threshold)
        - Warning message if content was truncated, None otherwise
        
    Example:
        content, warning = readfile("myfile.py", token_threshold=500)
        if warning:
            print(warning)  # Shows truncation message
        print(content)  # Shows numbered lines
    """
    try:
        with open(filepath, 'r') as file:
            data = file.readlines()
    except FileNotFoundError:
        return f"File not found: {filepath}", None
    except Exception as e:
        return f"Error reading file {filepath}: {str(e)}", None
        
    # Add line numbers
    numbered_lines = [f"{i:04}: {line}" for i, line in enumerate(data)]
    
    # Check total tokens
    full_content = "\n".join(numbered_lines)
    total_tokens = estimate_tokens(full_content)
    
    if total_tokens <= token_threshold:
        return full_content, None
        
    # If over threshold, include as many lines as possible
    current_tokens = 0
    included_lines = []
    
    for line in numbered_lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > token_threshold:
            break
        included_lines.append(line)
        current_tokens += line_tokens
    
    warning = (f"File exceeds token threshold of {token_threshold}. "
               f"Showing {len(included_lines)} of {len(data)} lines "
               f"({current_tokens}/{total_tokens} tokens). "
               f"Use readlines({filepath}, start_line, end_line) "
               f"to read specific ranges.")
               
    return "\n".join(included_lines), warning


def git_fetch(
    blech_clust_path: str,
) -> str:
    """Fetch from git

    Inputs:
        - blech_clust_path : Path to blech_clust

    Returns:
        - Output from git fetch
    """
    cmd_str = f"git -C {blech_clust_path} fetch"
    out = os.popen(cmd_str).read()
    return out


def get_commit_history(
        blech_clust_path: str,
        max_num: int = 10,
) -> str:
    """Get the commit history

    Inputs:
        - blech_clust_path : Path to blech_clust
        - max_num : Maximum number of commits to show

    Returns:
        - Commit history
    """
    cmd_str = \
        f"git -C {blech_clust_path} log --graph  --pretty=format:'%C(auto)%h%d (%cr) %s' --abbrev-commit"
    out = os.popen(cmd_str).read()
    out = "\n".join(out.split("\n")[:max_num])
    return out


def get_current_git_commit(
        blech_clust_path: str,
) -> str:
    """Get the current git commit

    Inputs:
        - blech_clust_path : Path to blech_clust

    Returns:
        - Current commit
    """
    cmd_str = f"git -C {blech_clust_path} rev-parse HEAD"
    out = os.popen(cmd_str).read()
    return out


def change_git_commit(
        blech_clust_path: str,
        commit: str) -> str:
    """Change the current git commit
    Inputs:
        - Commit
    """
    # os.system(f"git checkout {commit}")
    git_fetch(blech_clust_path)
    cmd_str = f"git -C {blech_clust_path} checkout {commit}"
    out = os.popen(cmd_str).read()
    return out


def create_file(
        file_path: str,
        data: str,
) -> bool:
    """Create a file with given data

    Inputs:
        - file_path : Path to file
        - data : Data to write

    Returns:
        - True if successful, False otherwise
    """
    try:
        with open(file_path, 'w') as file:
            file.write(data)
        print(f"Data written to file: {file_path}")
        return True
    except Exception as e:
        print(f"Error writing to file: {file_path}")
        print(e)
        return False


def run_python_script(
        script_path: str,
) -> str:
    """Run a script

    Inputs:
        - script_path : Path to script

    Returns:
        - Output from script
    """
    out = os.popen(f"python {script_path}").read()
    return out


def run_bash_script(
        script_path: str,
) -> str:
    """Run a bash script

    Inputs:
        - script_path : Path to script

    Returns:
        - Output from script
    """
    out = os.popen(f"bash {script_path}").read()
    return out


# def read_merged_docstrings(repo_name: str) -> str:
#     """Read the merged docstrings JSON file from a repository
#
#     Inputs:
#         - repo_name : Name of repository (owner/repo)
#
#     Returns:
#         - Text containing merged docstrings data
#     """
#     # import json
#     repo_path = get_local_repo_path(repo_name)
#     docstrings_path = os.path.join(repo_path, 'file_index', 'data', 'merged_docstrings.json')
#
#     try:
#         with open(docstrings_path, 'r') as f:
#             return f.read()
#             # return json.load(f)
#     except FileNotFoundError:
#         print(f"Docstrings file not found at: {docstrings_path}")
#         return ''
#         # return {}
#     # except json.JSONDecodeError:
#     #     print(f"Error decoding JSON from: {docstrings_path}")
#     #     return {}

def read_merged_summary(repo_name: str) -> str:
    """Read the merged summary JSON file from a repository

    Inputs:
        - repo_name : Name of repository (owner/repo)

    Returns:
        - Text containing merged summary data
    """
    # import json
    repo_path = get_local_repo_path(repo_name)
    summary_path = os.path.join(
        repo_path, 'file_index', 'data', 'merged_summary.json')

    try:
        with open(summary_path, 'r') as f:
            return f.read()
        #     return json.load(f)

    except FileNotFoundError:
        print(f"Summary file not found at: {summary_path}")
        return ''
        # return {}
    # except json.JSONDecodeError:
    #     print(f"Error decoding JSON from: {summary_path}")
    #     return {}


def get_func_code(
        module_path: str,
        func_name: str,
) -> str:
    """Use simple search to get the code for a function

    Inputs:
        - module_path : Path to module
        - func_name : Name of function

    Returns:
        - Code for function
    """

    with open(module_path, 'r') as file:
        lines = file.readlines()

    # Find all function definitions
    import re
    match_pattern = re.compile(r'def\s+.*\(')
    func_defs = re.findall(match_pattern, "\n".join(lines))
    # Get line numbers for each function definition
    func_def_lines = [i for i, line in enumerate(
        lines) if match_pattern.findall(line)]
    func_def_line_map = {func_def_lines[i]: func_defs[i]
                         for i in range(len(func_defs))}

    # Find range of lines for wanted function
    for i, this_num in enumerate(func_def_lines):
        if func_name in func_def_line_map[this_num]:
            start_line = this_num
            try:
                end_line = func_def_lines[i+1] - 1
            except IndexError:
                end_line = len(lines)
            break

    # Get code for function
    code = "".join(lines[start_line:end_line])
    return code
