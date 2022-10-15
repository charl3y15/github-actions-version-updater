import os
import time
from collections.abc import Generator
from typing import Any

import github_action_utils as gha_utils  # type: ignore
import requests
import yaml

from .config import ActionEnvironment, Configuration
from .run_git import (
    configure_git_author,
    create_new_git_branch,
    git_commit_changes,
    git_has_changes,
)
from .utils import (
    add_git_diff_to_job_summary,
    create_pull_request,
    display_whats_new,
    get_request_headers,
)


class GitHubActionsVersionUpdater:
    """Check for GitHub Action updates"""

    github_api_url = "https://api.github.com"
    github_url = "https://github.com/"
    workflow_action_key = "uses"

    def __init__(self, env: ActionEnvironment, user_config: Configuration):
        self.env = env
        self.user_config = user_config

    def run(self) -> None:
        """Entrypoint to the GitHub Action"""
        workflow_paths = self.get_workflow_paths()
        pull_request_body_lines = set()

        if not workflow_paths:
            gha_utils.warning(
                f'No Workflow found in "{self.env.repository}". '
                "Skipping GitHub Actions Version Update"
            )
            raise SystemExit(0)

        ignore_actions = self.user_config.ignore_actions

        if ignore_actions:
            gha_utils.echo(f'Actions "{ignore_actions}" will be skipped')

        for workflow_path in workflow_paths:
            workflow_updated = False

            try:
                with open(workflow_path, "r+") as file, gha_utils.group(
                    f'Checking "{workflow_path}" for updates'
                ):
                    file_data = file.read()
                    updated_workflow_data = file_data

                    data = yaml.load(file_data, Loader=yaml.FullLoader)
                    all_action_set = set(self.get_all_actions(data))
                    # Remove ignored actions
                    all_action_set.difference_update(ignore_actions)

                    for action in all_action_set:
                        try:
                            action_repository, version = action.split("@")
                        except ValueError:
                            gha_utils.warning(
                                f'Action "{action}" is in a wrong format, '
                                "We only support community actions currently"
                            )
                            continue

                        latest_release = self.get_latest_release(action_repository)

                        if not latest_release:
                            continue

                        updated_action = (
                            f'{action_repository}@{latest_release["tag_name"]}'
                        )

                        if action != updated_action:
                            gha_utils.echo(
                                f'Found new version for "{action_repository}"'
                            )
                            pull_request_body_lines.add(
                                self.generate_pull_request_body_line(
                                    action_repository, latest_release
                                )
                            )
                            gha_utils.echo(
                                f'Updating "{action}" with "{updated_action}"'
                            )
                            updated_workflow_data = updated_workflow_data.replace(
                                action, updated_action
                            )
                            workflow_updated = True
                        else:
                            gha_utils.echo(
                                f'No updates found for "{action_repository}"'
                            )

                    if workflow_updated:
                        file.seek(0)
                        file.write(updated_workflow_data)
                        file.truncate()
            except Exception:
                gha_utils.echo(f'Skipping "{workflow_path}"')

        if git_has_changes():
            # Use timestamp to ensure uniqueness of the new branch
            pull_request_body = "### GitHub Actions Version Updates\n" + "".join(
                pull_request_body_lines
            )
            gha_utils.append_job_summary(pull_request_body)

            if not self.user_config.skip_pull_request:
                new_branch_name = f"gh-actions-update-{int(time.time())}"
                create_new_git_branch(self.env.base_branch, new_branch_name)
                git_commit_changes(
                    self.user_config.commit_message,
                    self.user_config.git_commit_author,
                    new_branch_name,
                )
                create_pull_request(
                    self.user_config.pull_request_title,
                    self.env.repository,
                    self.env.base_branch,
                    new_branch_name,
                    pull_request_body,
                    self.user_config.github_token,
                )
            else:
                add_git_diff_to_job_summary()
                gha_utils.error(
                    "Updates found but skipping pull request. "
                    "Checkout build summary for details"
                )
                raise SystemExit(1)
        else:
            gha_utils.notice("Everything is up-to-date! \U0001F389 \U0001F389")

    def generate_pull_request_body_line(
        self, action_repository: str, latest_release: dict[str, str]
    ) -> str:
        """Generate pull request body line for pull request body"""
        return (
            f"* **[{action_repository}]({self.github_url + action_repository})** "
            "published a new release "
            f"[{latest_release['tag_name']}]({latest_release['html_url']}) "
            f"on {latest_release['published_at']}\n"
        )

    def get_latest_release(self, action_repository: str) -> dict[str, str]:
        """Get the latest release using GitHub API"""
        url = f"{self.github_api_url}/repos/{action_repository}/releases/latest"

        response = requests.get(
            url, headers=get_request_headers(self.user_config.github_token)
        )
        data = {}

        if response.status_code == 200:
            response_data = response.json()

            data = {
                "published_at": response_data["published_at"],
                "html_url": response_data["html_url"],
                "tag_name": response_data["tag_name"],
                "body": response_data["body"],
            }
        else:
            # if there is no previous release API will return 404 Not Found
            gha_utils.warning(
                f"Could not find any release for "
                f'"{action_repository}", status code: {response.status_code}'
            )

        return data

    def get_workflow_paths(self) -> list[str]:
        """Get all workflows of the repository using GitHub API"""
        url = f"{self.github_api_url}/repos/{self.env.repository}/actions/workflows"

        response = requests.get(
            url, headers=get_request_headers(self.user_config.github_token)
        )

        if response.status_code == 200:
            return [workflow["path"] for workflow in response.json()["workflows"]]

        gha_utils.error(
            f"An error occurred while getting workflows for"
            f"{self.env.repository}, status code: {response.status_code}"
        )
        raise SystemExit(1)

    def get_all_actions(self, data: Any) -> Generator[str, None, None]:
        """Recursively get all action names from workflow data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == self.workflow_action_key:
                    yield value
                elif isinstance(value, dict) or isinstance(value, list):
                    yield from self.get_all_actions(value)

        elif isinstance(data, list):
            for element in data:
                yield from self.get_all_actions(element)


if __name__ == "__main__":
    with gha_utils.group("Parse Configuration"):
        user_configuration = Configuration.create(os.environ)
        action_environment = ActionEnvironment.from_env(os.environ)

        gha_utils.echo("Using Configuration:")
        gha_utils.echo(user_configuration._asdict())

    # Configure Git Author
    configure_git_author(
        user_configuration.git_committer_username,
        user_configuration.git_committer_email,
    )

    with gha_utils.group("Run GitHub Actions Version Updater"):
        actions_version_updater = GitHubActionsVersionUpdater(
            action_environment,
            user_configuration,
        )
        actions_version_updater.run()

    display_whats_new()
