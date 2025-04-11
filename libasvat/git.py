import re
import os
import stat
import click
import shutil
import traceback
import subprocess


def git(*args, **kwargs):
    """Generic method to execute git. This runs git with the given list of var-args and keyword-args.

    The given ARGS is a list of arguments to pass to the command, following the common format of subprocess method calls.
    The given KWARGS is a dict of key:value options to this method (defined below), and they are also passed along to the
    `subprocess.run()` method.

    This returns the `subprocess.CompletedProcess` value from `subprocess.run`.

    An 'output' flag can be used to make this method capture git's output as text. The text output is available in return.stdout

    This method always uses `subprocess.run` to run the given command, changing some parameters as required by the given options.
    This always runs the command checking the output result [run(check=True)], which means raising exception if the command fails,
    unless the flag `dont_check=True` is given."""
    command = ["git"] + list(args)

    dont_check = kwargs.pop("dont_check", False)
    use_output = kwargs.pop("output", False)

    result = subprocess.run(command, text=bool(use_output), capture_output=bool(use_output), check=(not dont_check), **kwargs)
    return result


def clone(*args, **kwargs):
    """Utility method to call GIT CLONE.

    If `shallow_clone` is true, then the flags '--depth=1' and '--no-single-branch' will be used to perform a shallow clone."""
    cmd = ["clone"] + list(args)
    if kwargs.pop("shallow_clone", False):
        cmd.append("--depth=1")
        cmd.append("--no-single-branch")
    return git(*cmd, **kwargs)


def shallow_clone(*args, **kwargs):
    """Utility method to call GIT CLONE using shallow cloning."""
    return clone(*args, **kwargs, shallow_clone=True)


def submodule_update(*args, **kwargs):
    """Utility method to call GIT SUBMODULE UPDATE"""
    cmd = ["submodule", "update"] + list(args)
    return git(*cmd, **kwargs)


def checkout(*args, **kwargs):
    """Utility method to call GIT CHECKOUT"""
    cmd = ["checkout"] + list(args)
    return git(*cmd, **kwargs)


def update_to_branch(branch_name, verbose=False):
    """Changes current branch to the given BRANCH_NAME, and then updates the repository
    by pulling new changes and initializing/updating all submodules recursively."""
    checkout(branch_name, output=not verbose)
    pull(output=not verbose)
    submodule_update("--init", "--recursive", output=not verbose)


def create_branch(branch_name, verbose=False):
    """Creates a new branch with the given name.
    Note: the current branch will be changed to this newly created one."""
    return checkout("-b", branch_name, output=not verbose)


def are_branches_equal(branch_a, branch_b):
    """Compares two local branches, returning True if branches are equal, False otherwise."""
    result = git("diff", "--quiet", branch_a, branch_b, dont_check=True)
    return result.returncode == 0


def does_branch_exist(branch_name, check_in_origin=True):
    """Checks if a branch with the given BRANCH_NAME exists.

    By default, CHECK_IN_ORIGIN is true, which means we'll check if the branch exists in the remote repository.
    Otherwise, if CHECK_IN_ORIGIN is false, we'll check if the branch exists in the local repository."""
    # Note: this may not be the best way to check if a branch exists... But for now it should work.
    # Note2: normally this only works to check if a branch exists locally. To check for remote branches,
    # we need to prepend 'origin/' in the branch_name (use 'check_in_origin' arg flag).
    if check_in_origin:
        branch_name = "origin/" + branch_name
    result = git("diff", "--quiet", branch_name, branch_name, dont_check=True)
    return result.returncode == 0


def delete_branch(branch_name, force=False, remove_from_remote=False, verbose=False):
    """Deletes the branch BRANCH_NAME from the local repository.

    If FORCE is True, will force deletion of branch (using -D flag instead of -d) regardless of any un-merged commits in the branch.

    If REMOVE_FROM_REMOTE is True, this will also delete this branch from the remote repository."""
    delete_flag = "-D" if force else "-d"
    git("branch", delete_flag, branch_name, output=not verbose)
    if remove_from_remote:
        git("push", "-d", "origin", branch_name, output=not verbose)


def pull(*args, **kwargs):
    """Utility method to call GIT PULL"""
    cmd = ["pull"] + list(args)
    return git(*cmd, **kwargs)


def get_last_remote_commit(url, branch="master"):
    """Gets the hash code of the last commit in the given BRANCH of the given repository URL.

    This is executed using `git ls-remote`, so there is NO cloning of the repository - it checks directly the remote repository.
    As such its fairly fast to run."""
    cmd = ["ls-remote", url]
    result = git(*cmd, output=True, dont_check=True)
    if result.returncode == 0:
        output = result.stdout.splitlines()
        for line in output:
            if f"refs/heads/{branch}" in line:
                return line.split()[0]


def commit(*args, **kwargs):
    """Utility method to call GIT COMMIT"""
    cmd = ["commit"] + list(args)
    return git(*cmd, **kwargs)


def commit_all_changes(message, verbose=False):
    """Adds all changes in the repository and commits them with the given MESSAGE."""
    git("add", ".", output=not verbose)
    commit("-m", message, dont_check=True, output=not verbose)


def push(*args, **kwargs):
    """Utility method to call GIT PUSH"""
    cmd = ["push"] + list(args)
    return git(*cmd, **kwargs)


def merge(*args, **kwargs):
    """Utility method to call GIT MERGE"""
    cmd = ["merge"] + list(args)
    return git(*cmd, **kwargs)


def merge_to_target(source_branch, target_branch, disable_push=False, delete_source_branch=False, verbose=False):
    """Merges the local SOURCE_BRANCH into the TARGET_BRANCH branch, and pushes all changes to the remote repository.

    This returns False if any of the branches doesn't exist, or if SOURCE_BRANCH is equal to TARGET_BRANCH. Otherwise returns True
    if the branch was merged into TARGET_BRANCH.

    If DISABLE_PUSH is True, the local TARGET_BRANCH branch changes (due to the merge) aren't pushed to the remote.

    If DELETE_SOURCE_BRANCH is true, the SOURCE_BRANCH is deleted from the local rep.
    """
    if not does_branch_exist(source_branch, check_in_origin=False):
        return False
    if not does_branch_exist(target_branch, check_in_origin=False):
        return False
    update_to_branch(target_branch, verbose=verbose)
    has_changes = not are_branches_equal(target_branch, source_branch)
    if has_changes:
        merge("--no-ff", source_branch, output=not verbose)
        if not disable_push:
            push("origin", target_branch, output=not verbose)
    if delete_source_branch:
        # we assume the source_branch is local, so remove it only from local rep.
        delete_branch(source_branch, force=True, verbose=verbose)
    return has_changes


def merge_to_master(source_branch, disable_push=False, delete_source_branch=False, verbose=False):
    """Merges the local SOURCE_BRANCH into the MASTER branch, and pushes all changes to the remote repository.

    This returns False if SOURCE_BRANCH doesn't exist, or if SOURCE_BRANCH is equal to MASTER. Otherwise returns True
    if the branch was merged into master.

    If DISABLE_PUSH is True, the local master branch changes (due to the merge) aren't pushed to the remote."""
    return merge_to_target(source_branch, "master", disable_push=disable_push, delete_source_branch=delete_source_branch, verbose=verbose)


def get_tags() -> list[str]:
    """Gets a list of all tags of the current repository. They are ordered FIRST->LATEST"""
    result = git("tag", "-l", "--sort=creatordate", output=True)
    return result.stdout.strip().splitlines()


def get_latest_tag() -> str:
    """Gets the latest tag in the current repository.

    May return None if no tags are defined in this repository.
    """
    result = git("describe", "--tags", "--abbrev=0", output=True, dont_check=True)
    if result.returncode == 0:
        return result.stdout.strip()


def select_tag(tag_name, offset=0, filter=None):
    """Checks if the given TAG_NAME exists in the list of tags of this repository.

    If TAG_NAME exists, this method gets the index of TAG_NAME in all tags, adds OFFSET to it, and returns that tag
    instead, if it exists (is a valid index). Examples below.
    If TAG_NAME doesn't exist, and OFFSET is negative, this method returns the tag with the index OFFSET from all tags.
    Otherwise, this returns None.

    Examples: assume a list of all tags `[A, B, C]`:
    * `get_tag(C)` would return C  (same goes for A or B).
    * `get_tag(B, offset=1)` would also return C, since that is the "B + 1" tag (or the next tag after B).
    * `get_tag(C, offset=-1)` would return B, since that is the "C - 1" tag (or the previous tag from C).
    * `get_tag(A, offset=-1)` would return None, since the final index would be -1, or "before A", which doesn't exist.
    * `get_tag(D)` would return None, since D doesnt exist.
    * `get_tag(D, offset=-1)` would return C, since in this case offset is used as index, thus getting the last item.

    If FILTER is given, it should be a string. Then the list of all tags is filtered to only contain tags that contain
    FILTER in them. The rest of this method operates on this filtered tags list.
    """
    tags = get_tags()
    if filter is not None:
        tags = [t for t in tags if filter in t]
    if tag_name in tags:
        index = tags.index(tag_name) + offset
        if 0 <= index < len(tags):
            return tags[index]
    elif offset < 0 and abs(offset) <= len(tags):
        # if offset is a valid negative index
        return tags[offset]
    return None


def get_commits_between(start, end="HEAD", include_merges=True, include_regulars=True):
    """Gets a list of hashes of all commits between the START and END markers.

    This matches running `git log START..END`. The START/END markers therefore may be a tag, commit, branch or HEAD.

    If INCLUDE_MERGES is true, then merge commits are included in the result.
    If INCLUDE_REGULARS is true, then normal (non-merge) commits are included in the result.
    Therefore, if both INCLUDE_MERGES and INCLUDE_REGULARS are true (the default), all commits in the range are included
    in the result. Thus changing one of the flags to False will filter some commits out, while using both flags as False
    will return a empty list.

    The returned list of hashes is ordered as LATEST->OLDEST
    """
    hashes: list[str] = []
    cmd = [
        "log",
        f"{start}..{end}",
        "--oneline",
    ]
    if include_regulars and include_merges:
        pass  # no need to change command
    elif include_merges:
        cmd.append("--merges")
    elif include_regulars:
        cmd.append("--no-merges")
    else:  # both flags are false
        return hashes
    result = git(*cmd, output=True)
    for commit_line in result.stdout.splitlines():
        # oneliners format: '<hash> (...) <msg>'
        # the (...) section is optional (depends on commit), and may contain data such as tag name, branch name, HEAD pos)
        hash = commit_line.strip().split()[0]
        hashes.append(hash)
    return hashes


def get_commit_message(commit_hash) -> list[str]:
    """Gets the full commit message.

    Returns a list of strings, of each line of text in the message, or None if couldn't get the commit message.
    """
    result = git("show", "-s", "--format=%B", commit_hash, output=True, dont_check=True)
    if result.returncode == 0:
        return result.stdout.strip().splitlines()


def build_message_from_commits(commits, rep_name=None):
    """Builds a list of Markdown-formatted strings containing the message of all given COMMITS.

    PR Merge commit messages are replaced with a link to the PR.

    If REP_NAME is given, it should be the repository name from where COMMITS came from.
    Then, any "Merged PR" commits in the list are displayed in the result as `PR: <url>` instead
    of displaying the regular commit message. The `<url>` is the URL to the PR page in git.
    """
    msg: list[str] = []
    for commit_hash in commits:
        lines = get_commit_message(commit_hash)
        if len(lines) <= 0:
            lines.append(f"<no-commit-msg: {commit_hash}>")

        # TODO: recognize merge commits? might differ based on git service provider (bitbucket, github, etc)
        # Regular commit
        msg.append(f"* {lines[0]}")
        for sub_line in lines[1:]:
            msg.append(f"    * {sub_line}")
    return msg


def create_tag(tag_name, push=True, verbose=False):
    """Creates a new tag TAG_NAME marking the current state of the repository.
    If a tag with the given name already exists, it is deleted, and then recreated.

    If PUSH is true, will also push the newly created tag to the remote repository.
    """
    tags = get_tags()
    for tag in tags:
        if tag_name == str(tag).replace("\n", ""):
            git("tag", "-d", tag_name, output=not verbose)
            if push:
                git("push", "origin", f":{tag_name}", output=not verbose)
    git("tag", tag_name, output=not verbose)
    if push:
        git("push", "origin", tag_name, output=not verbose)


class Repository:
    """Utility class to represent a Git repository and simplify its usage.

    This is intended to be used as a context-manager:
    ```python
    with Repository(...) as rep:
        # do stuff in the repository
        pass
    ```
    Regardless of options, using Repository as a context-manager will already trigger `self.clone()` on `__enter__`, and then
    `self.delete()` on `__exit__`.


    When using `Repository(auto=True)`, it's the same as:
    ```python
    with Repository(...) as rep:
        # shallow clone
        rep.update(rep.auto_edit_branch)
        # do stuff in the repository
        rep.delete()
    ```

    When using `Repository(auto=True, editable=True)`, it's the same as:
    ```python
    with Repository(...) as rep:
        # full clone
        rep.update(rep.auto_edit_branch)
        # do stuff in the repository
        rep.create_branch(rep.auto_edit_changes_branch)
        rep.commit_all_changes(rep.auto_edit_commit_msg)
        rep.merge(source, target) # rep.auto_edit_changes_branch -> rep.auto_edit_branch
        rep.delete()
    ```
    """

    def __init__(self, url, name, branch="master", destination=None, editable=False, auto=False, disable_ops=None, verbose=False):
        """* NAME: name of the repository.
        * BRANCH: the initial value for the `auto_edit_branch` attribute, indicating which branch of the repository to use.
        * DESTINATION: custom folder name for the repository. Defaults to the repository name.
        * EDITABLE: if this repository is editable - if changes can be made to it and sent to the remote.
        * AUTO: if auto commands are enabled when using as a context-manager.
        * VERBOSE: if git commands output are also printed

        DISABLE_OPS is a set (or other object that accepts `X in disable_ops`) that defines which git operations will be disabled. Possible values:
            * `clone`: disables cloning a missing repository. Note that if the rep doesn't exist, an error will occur.
            * `branch`: disables creating a new branch. Any changes are then commited to whatever the current branch is.
            * `commit`: disables commiting changes. Consequently merge/push doesn't happen as well.
            * `merge`: disables merging the new branch into master. The new branch will continue only locally. Only applicable when a new branch was
            created.
            * `push`: disables pushing the changes to the remote branch. The remote branch is either master (if used a new branch and merged it) or
            the current branch of the rep.
            * `delete`: disables deleting the repository after using it (which happens if repo was cloned by us).
        """
        # TODO: get name from url?
        self.name: str = name
        self.destination: str = destination
        self.url = url
        self.editable = editable
        self.auto = auto
        self.disable_ops: set[str] = disable_ops if disable_ops is not None else set()
        self._enter_cwd = None
        self._remove_rep = False
        self.auto_edit_branch = branch
        self.auto_edit_changes_branch = "autoUpdates"
        self.auto_edit_commit_msg = "Updated rep via libasvat's auto-edit"
        self.verbose = verbose
        self.submodules: list[dict[str, str]] = []

    @property
    def path(self):
        """The name of the repository folder."""
        if self.destination is not None:
            if os.path.isdir(self.name) and not os.path.isdir(self.destination):
                # Edge-case: when trying to use a custom destination, but the rep already exists in the default path,
                # use it and ignore the destination in order to improve efficiency (no need to clone the same rep).
                return self.name
            return self.destination
        return self.name

    @property
    def full_path(self):
        """Full absolute path to this repository."""
        return os.path.join(self._enter_cwd, self.path)

    def exists(self):
        """Checks if the folder of this repository existed in the current working directory."""
        return os.path.isdir(self.name) or (self.destination is not None and os.path.isdir(self.destination))

    def clone(self):
        """Starts up this repository instance by cloning the repository. This is required for all other operations to work.

        If the rep doesn't exist in the current working directory (CWD), this will clone the rep. Cloning is shallow if
        we're not editable.

        Afterwards, the CWD is changed to the repository, thus enabling the other methods of this class.
        """
        self._enter_cwd = os.getcwd()
        if not self.exists():
            if "clone" not in self.disable_ops:
                cmd = [self.url]
                if self.destination is not None:
                    cmd.append(self.destination)

                msg = "Shallow-cloning" if not self.editable else "Cloning"
                click.secho(f"{self}: {msg} repository...", fg="blue")
                clone(*cmd, shallow_clone=not self.editable)
                click.secho(f"{self}: Successfully cloned repository to '{self.full_path}'", fg="green")

                self._remove_rep = True
            else:
                raise FileNotFoundError(f"Missing local repository '{self.path}'")
        else:
            click.secho(f"{self}: repository already exists at '{self.full_path}'", fg="yellow")
        os.chdir(self.path)
        self._load_submodules()

    def _load_submodules(self):
        """Loads gitmodules data from the current repository.

        The current working directory must be the root of a repository.
        """
        self.submodules = []
        current = {}
        if not os.path.isfile(".gitmodules"):
            return
        with open(".gitmodules") as gitmodules:
            contents = gitmodules.readlines()
        for line in contents:
            if line.startswith("[submodule"):
                if len(current) > 0:
                    self.submodules.append(current)
                match = re.search(r"\[submodule\s+[\"](.+)[\"]\]", line)
                current = {
                    "name": match.group(1)
                }
            else:
                parts = [s.strip() for s in line.split("=")]
                name = parts[0]
                if len(name) > 0:
                    value = "".join(parts[1:])
                    if name == "path":
                        value = value.replace("\\", "/").replace("/", os.path.sep)
                    current[name] = value
        if len(current) > 0:
            self.submodules.append(current)

    def delete(self):
        """Deletes the local repository from disk, if it was cloned by our `self.clone()`."""
        if self._remove_rep and "delete" not in self.disable_ops:
            click.secho(f"{self}: removing downloaded repository.", fg="blue")

            def del_rw(action, name, exc):
                os.chmod(name, stat.S_IWRITE)
                os.remove(name)
            shutil.rmtree(self.path, onerror=del_rw)

    def update(self, branch="master"):
        """Fully updates the repository to the given BRANCH.

        Checkouts to BRANCH, pulls all changes and updates/inits all submodules recursively.
        """
        click.secho(f"{self}: Updating repository to '{branch}'...", fg="blue")
        git("fetch", "--all", output=not self.verbose)
        checkout(branch, output=not self.verbose)
        pull(output=not self.verbose, dont_check=True)
        click.secho(f"{self}: Updating submodules in repository...", fg="blue")
        submodule_update("--init", "--recursive", output=not self.verbose)

    def create_branch(self, branch_name):
        """Creates a new BRANCH_NAME branch, and checkouts to it."""
        click.secho(f"{self}: creating branch {branch_name}", fg="blue")
        create_branch(branch_name, verbose=self.verbose)

    def commit_all_changes(self, commit_message):
        """Commits all changes (`git add .`) with the given COMMIT_MESSAGE to the current branch."""
        click.secho(f"{self}: commiting all changes: {commit_message}.", fg="blue")
        commit_all_changes(commit_message, verbose=self.verbose)

    def merge(self, source_branch, target_branch):
        """Merges the local SOURCE_BRANCH to the local TARGET_BRANCH, then pushes the updated TARGET_BRANCH to the remote,
        and deletes the local SOURCE_BRANCH.
        """
        if "merge" in self.disable_ops or not self.editable:
            return
        click.secho(f"{self}: merging '{source_branch}' into '{target_branch}'...", fg="blue")
        disable_push = "push" in self.disable_ops
        if merge_to_target(source_branch, target_branch, disable_push=disable_push, delete_source_branch=True, verbose=self.verbose):
            click.secho(f"{self}: changes merged into '{target_branch}'!", fg="green")
        else:
            click.secho(f"{self}: no new changes to push to '{target_branch}'.", fg="yellow")

    def push(self):
        """Calls GIT PUSH to push all current changes to the remote rep."""
        if "push" not in self.disable_ops and self.editable:
            push(output=not self.verbose)
            click.secho(f"{self}: changes pushed to current branch.", fg="green")

    def create_tag(self, tag_name):
        """Creates a new tag TAG_NAME marking the current state of the repository.
        If a tag with the given name already exists, it is deleted, and then recreated."""
        if self.editable:
            create_tag(tag_name, verbose=self.verbose)
            click.secho(f"{self}: created tag '{tag_name}'", fg="green")

    def get_latest_tag(self):
        """Gets the latest tag in the current repository.

        May return None if no tags are defined in this repository."""
        return get_latest_tag()

    def get_tag(self, tag_name, offset=0, filter=None):
        """Checks if the given TAG_NAME exists in the list of tags of this repository.

        If TAG_NAME exists, this method gets the index of TAG_NAME in all tags, adds OFFSET to it, and returns that tag
        instead, if it exists (is a valid index). Examples below.
        If TAG_NAME doesn't exist, and OFFSET is negative, this method returns the tag with the index OFFSET from all tags.
        Otherwise, this returns None.

        Examples: assume a list of all tags `[A, B, C]`:
        * `get_tag(C)` would return C  (same goes for A or B).
        * `get_tag(B, offset=1)` would also return C, since that is the "B + 1" tag (or the next tag after B).
        * `get_tag(C, offset=-1)` would return B, since that is the "C - 1" tag (or the previous tag from C).
        * `get_tag(A, offset=-1)` would return None, since the final index would be -1, or "before A", which doesn't exist.
        * `get_tag(D)` would return None, since D doesnt exist.
        * `get_tag(D, offset=-1)` would return C, since in this case offset is used as index, thus getting the last item.

        If FILTER is given, it should be a string. Then the list of all tags is filtered to only contain tags that contain
        FILTER in them. The rest of this method operates on this filtered tags list.
        """
        return select_tag(tag_name, offset=offset, filter=filter)

    def get_commits_between(self, start, end="HEAD", include_merges=True, include_regulars=True):
        """Gets a list of hashes of all commits between the START and END markers.

        This matches running `git log START..END`. The START/END markers therefore may be a tag, commit, branch or HEAD.

        If INCLUDE_MERGES is true, then merge commits are included in the result.
        If INCLUDE_REGULARS is true, then normal (non-merge) commits are included in the result.
        Therefore, if both INCLUDE_MERGES and INCLUDE_REGULARS are true (the default), all commits in the range are included
        in the result. Thus changing one of the flags to False will filter some commits out, while using both flags as False
        will return a empty list.

        The returned list of hashes is ordered as LATEST->OLDEST
        """
        return get_commits_between(start, end=end, include_merges=include_merges, include_regulars=include_regulars)

    def build_message_from_commits(self, start, end="HEAD"):
        """Builds a list of Markdown-formatted strings, containing the messages of all commits from the START point (a hash, branch or tag)
        to the END point of the repository.

        PR Merge commit messages are replaced with a link to the PR.
        """
        commits = self.get_commits_between(start, end=end)
        return build_message_from_commits(commits, rep_name=self.name)

    def get_all_submodule_paths(self):
        """Gets a list of all submodule paths"""
        paths: list[str] = []
        for module in self.submodules:
            paths.append(module["path"])
        return paths

    def get_submodule_info(self, rep_name):
        """Gets the submodule info dict with the given repository name REP_NAME, if it exists."""
        # TODO: verify this works
        # Trying to get last word on URL to match to REP_NAME, excluding '.git' suffix
        pattern = "([^./]+)[.]?[g]?[i]?[t]?$"

        for module in self.submodules:
            match = re.search(pattern, module["url"])
            if match:
                module_rep_name = match.group(1)
                if module_rep_name == rep_name:
                    return module

    def get_submodule(self, rep_name, editable=False):
        """Gets a git.Repository object pointing to a submodule of this rep, based on the given REP_NAME.

        The submodule Repository object is created with the given EDITABLE flag, and other default values (such as auto=False).
        """
        sub_info = self.get_submodule_info(rep_name)
        return Repository(rep_name, destination=sub_info["path"], editable=editable)

    def __enter__(self):
        self._enter_cwd = os.getcwd()

        self.clone()
        if self.auto:
            self.update(self.auto_edit_branch)
        click.secho(f"{self}: opening local repository (editable={self.editable})", fg="blue")

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        finished_ok = True
        if exc_type is not None:
            click.secho("".join(traceback.format_exception(exc_type, exc_value, exc_tb)), fg="red")
            finished_ok = False

        if self.auto and self.editable and "commit" not in self.disable_ops:
            if finished_ok:
                created_branch = False
                if "branch" not in self.disable_ops:
                    self.create_branch(self.auto_edit_changes_branch)
                    created_branch = True
                self.commit_all_changes(self.auto_edit_commit_msg)
                if created_branch and "merge" not in self.disable_ops:
                    self.merge(self.auto_edit_changes_branch, self.auto_edit_branch)
                elif (not created_branch) and "push" not in self.disable_ops:
                    self.push()
            else:
                click.secho(f"{self}: skipping auto-edit exit operations due to previous error.", fg="yellow")

        click.secho(f"{self}: Closing local repository.", fg="blue")

        os.chdir(self._enter_cwd)

        if not self.editable or (self.editable and finished_ok):
            self.delete()

    def __repr__(self):
        return f"GitRep({self.name})"

    def __str__(self):
        return f"GitRep '{self.path}'"
