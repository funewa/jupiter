"""The command for finding projects."""
from dataclasses import dataclass
from typing import Optional, List

from jupiter.domain.projects.project import Project
from jupiter.domain.projects.project_key import ProjectKey
from jupiter.framework.use_case import (
    UseCaseArgsBase,
    UseCaseResultBase,
    ProgressReporter,
)
from jupiter.use_cases.infra.use_cases import AppReadonlyUseCase, AppUseCaseContext


class ProjectFindUseCase(
    AppReadonlyUseCase["ProjectFindUseCase.Args", "ProjectFindUseCase.Result"]
):
    """The command for finding projects."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        allow_archived: bool
        filter_keys: Optional[List[ProjectKey]]

    @dataclass(frozen=True)
    class Result(UseCaseResultBase):
        """Result object."""

        projects: List[Project]

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> "Result":
        """Execute the command's action."""
        workspace = context.workspace

        with self._storage_engine.get_unit_of_work() as uow:
            project_collection = uow.project_collection_repository.load_by_parent(
                workspace.ref_id
            )
            projects = uow.project_repository.find_all_with_filters(
                parent_ref_id=project_collection.ref_id,
                allow_archived=args.allow_archived,
                filter_keys=args.filter_keys,
            )

        return self.Result(projects=list(projects))
