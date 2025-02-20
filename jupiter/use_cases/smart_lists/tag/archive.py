"""The command for archiving a smart list tag."""
import logging
from dataclasses import dataclass
from typing import Final

from jupiter.domain.smart_lists.infra.smart_list_notion_manager import (
    SmartListNotionManager,
    NotionSmartListTagNotFoundError,
)
from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.event import EventSource
from jupiter.framework.update_action import UpdateAction
from jupiter.framework.use_case import (
    MutationUseCaseInvocationRecorder,
    UseCaseArgsBase,
    ProgressReporter,
    MarkProgressStatus,
)
from jupiter.use_cases.infra.use_cases import (
    AppUseCaseContext,
    AppMutationUseCase,
)
from jupiter.utils.time_provider import TimeProvider

LOGGER = logging.getLogger(__name__)


class SmartListTagArchiveUseCase(
    AppMutationUseCase["SmartListTagArchiveUseCase.Args", None]
):
    """The command for archiving a smart list tag."""

    @dataclass(frozen=True)
    class Args(UseCaseArgsBase):
        """Args."""

        ref_id: EntityId

    _smart_list_notion_manager: Final[SmartListNotionManager]

    def __init__(
        self,
        time_provider: TimeProvider,
        invocation_recorder: MutationUseCaseInvocationRecorder,
        storage_engine: DomainStorageEngine,
        smart_list_notion_manager: SmartListNotionManager,
    ) -> None:
        """Constructor."""
        super().__init__(time_provider, invocation_recorder, storage_engine)
        self._smart_list_notion_manager = smart_list_notion_manager

    def _execute(
        self,
        progress_reporter: ProgressReporter,
        context: AppUseCaseContext,
        args: Args,
    ) -> None:
        """Execute the command's action."""
        workspace = context.workspace

        with self._storage_engine.get_unit_of_work() as uow:
            smart_list_collection = uow.smart_list_collection_repository.load_by_parent(
                workspace.ref_id
            )
            smart_list_tag = uow.smart_list_tag_repository.load_by_id(args.ref_id)

            smart_list_items = uow.smart_list_item_repository.find_all_with_filters(
                parent_ref_id=smart_list_tag.smart_list_ref_id,
                allow_archived=True,
                filter_tag_ref_ids=[args.ref_id],
            )

        for smart_list_item in smart_list_items:
            with progress_reporter.start_updating_entity(
                "smart list item", smart_list_item.ref_id, str(smart_list_item.name)
            ) as entity_reporter:
                with self._storage_engine.get_unit_of_work() as uow:
                    smart_list_item = smart_list_item.update(
                        name=UpdateAction.do_nothing(),
                        is_done=UpdateAction.do_nothing(),
                        tags_ref_id=UpdateAction.change_to(
                            [t for t in smart_list_item.tags_ref_id if t != args.ref_id]
                        ),
                        url=UpdateAction.do_nothing(),
                        source=EventSource.CLI,
                        modification_time=self._time_provider.get_current_time(),
                    )
                    uow.smart_list_item_repository.save(smart_list_item)
                    entity_reporter.mark_local_change()

        with progress_reporter.start_archiving_entity(
            "smart list tag", smart_list_tag.ref_id
        ) as entity_reporter:
            entity_reporter.mark_known_name(str(smart_list_tag.tag_name))

            with self._storage_engine.get_unit_of_work() as uow:
                smart_list_tag = smart_list_tag.mark_archived(
                    EventSource.CLI, self._time_provider.get_current_time()
                )
                uow.smart_list_tag_repository.save(smart_list_tag)
                entity_reporter.mark_local_change()

            try:
                self._smart_list_notion_manager.remove_branch_tag(
                    smart_list_collection.ref_id,
                    smart_list_tag.smart_list_ref_id,
                    smart_list_tag.ref_id,
                )
                entity_reporter.mark_remote_change()
            except NotionSmartListTagNotFoundError:
                LOGGER.info(
                    "Skipping archival on Notion side because smart list was not found"
                )
                entity_reporter.mark_remote_change(MarkProgressStatus.FAILED)
