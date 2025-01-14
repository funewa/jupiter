"""Generic syncers between local and Notion."""
import logging
from dataclasses import dataclass
from typing import (
    TypeVar,
    Final,
    Generic,
    Any,
    Optional,
    Iterable,
    List,
    Type,
    Dict,
    cast,
    Union,
)

from jupiter.domain.storage_engine import DomainStorageEngine
from jupiter.domain.sync_prefer import SyncPrefer
from jupiter.domain.tag_name import TagName
from jupiter.framework.base.entity_id import EntityId
from jupiter.framework.base.timestamp import Timestamp
from jupiter.framework.entity import (
    LeafEntity,
    TrunkEntity,
    BranchEntity,
    BranchTagEntity,
)
from jupiter.framework.notion import (
    NotionRootEntity,
    NotionTrunkEntity,
    NotionBranchEntity,
    NotionLeafEntity,
    NotionBranchTagEntity,
)
from jupiter.framework.notion_manager import (
    ParentTrunkLeafNotionManager,
    NotionLeafEntityNotFoundError,
    ParentTrunkBranchLeafNotionManager,
    NotionBranchEntityNotFoundError,
    ParentTrunkBranchLeafAndTagNotionManager,
)
from jupiter.framework.use_case import ProgressReporter, MarkProgressStatus

LOGGER = logging.getLogger(__name__)


TrunkT = TypeVar("TrunkT", bound=TrunkEntity)
BranchT = TypeVar("BranchT", bound=BranchEntity)
LeafT = TypeVar("LeafT", bound=LeafEntity)
BranchTagT = TypeVar("BranchTagT", bound=BranchTagEntity)
NotionParentT = TypeVar(
    "NotionParentT", bound=Union[NotionRootEntity[Any], NotionTrunkEntity[Any]]
)
NotionTrunkT = TypeVar("NotionTrunkT", bound=NotionTrunkEntity[Any])
NotionBranchT = TypeVar("NotionBranchT", bound=NotionBranchEntity[Any])
NotionLeafT = TypeVar("NotionLeafT", bound=NotionLeafEntity[Any, Any, Any])
NotionBranchTagT = TypeVar("NotionBranchTagT", bound=NotionBranchTagEntity[Any])
NotionLeafDirectExtraInfoT = TypeVar("NotionLeafDirectExtraInfoT")
NotionLeafInverseExtraInfoT = TypeVar("NotionLeafInverseExtraInfoT")


@dataclass(frozen=True)
class SyncResult(Generic[LeafT]):
    """The result of a sync."""

    all: Iterable[LeafT]
    created_locally: List[LeafT]
    modified_locally: List[LeafT]
    created_remotely: List[LeafT]
    modified_remotely: List[LeafT]
    removed_remotely: List[EntityId]

    @property
    def has_a_local_change(self) -> bool:
        """Whether the sync operation did a local change."""
        return len(self.created_locally) > 0 or len(self.modified_locally) > 0


class TrunkLeafNotionSyncService(
    Generic[
        TrunkT,
        LeafT,
        NotionParentT,
        NotionTrunkT,
        NotionLeafT,
        NotionLeafDirectExtraInfoT,
        NotionLeafInverseExtraInfoT,
    ]
):
    """The service class for syncing a linked set of entities between local and Notion."""

    _trunk_type: Type[TrunkT]
    _leaf_type: Type[LeafT]
    _leaf_name: Final[str]
    _notion_leaf_type: Type[NotionLeafT]
    _storage_engine: Final[DomainStorageEngine]
    _notion_manager: ParentTrunkLeafNotionManager[
        NotionParentT,
        NotionTrunkT,
        NotionLeafT,
    ]

    def __init__(
        self,
        trunk_type: Type[TrunkT],
        leaf_type: Type[LeafT],
        leaf_name: str,
        notion_leaf_type: Type[NotionLeafT],
        storage_engine: DomainStorageEngine,
        notion_manager: ParentTrunkLeafNotionManager[
            NotionParentT,
            NotionTrunkT,
            NotionLeafT,
        ],
    ) -> None:
        """Constructor."""
        self._trunk_type = trunk_type
        self._leaf_type = leaf_type
        self._leaf_name = leaf_name
        self._notion_leaf_type = notion_leaf_type
        self._storage_engine = storage_engine
        self._notion_manager = notion_manager

    def sync(
        self,
        progress_reporter: ProgressReporter,
        parent_ref_id: EntityId,
        direct_info: NotionLeafDirectExtraInfoT,
        inverse_info: NotionLeafInverseExtraInfoT,
        drop_all_notion_side: bool,
        sync_even_if_not_modified: bool,
        filter_ref_ids: Optional[Iterable[EntityId]],
        sync_prefer: SyncPrefer,
    ) -> SyncResult[LeafT]:
        """Synchronise entities between Notion and local storage."""
        filter_ref_ids_set = frozenset(filter_ref_ids) if filter_ref_ids else None

        with self._storage_engine.get_unit_of_work() as uow:
            trunk: TrunkT = uow.get_trunk_repository_for(
                self._trunk_type
            ).load_by_parent(parent_ref_id)
            all_leaves = uow.get_leaf_repository_for(self._leaf_type).find_all(
                parent_ref_id=trunk.ref_id,
                allow_archived=True,
                filter_ref_ids=filter_ref_ids,
            )
        all_leaves_set: Dict[EntityId, LeafT] = {v.ref_id: v for v in all_leaves}

        if not drop_all_notion_side:
            all_notion_leaves = self._notion_manager.load_all_leaves(trunk.ref_id)
            all_notion_leaves_notion_ids = set(
                self._notion_manager.load_all_saved_notion_ids(trunk.ref_id)
            )
        else:
            self._notion_manager.drop_all_leaves(trunk.ref_id)
            all_notion_leaves = []
            all_notion_leaves_notion_ids = set()
        all_notion_leaves_set: Dict[EntityId, NotionLeafT] = {}

        created_locally = []
        modified_locally = []
        created_remotely = []
        modified_remotely = []
        removed_remotely = []

        # Explore Notion and apply to local
        for notion_leaf in all_notion_leaves:
            if (
                filter_ref_ids_set is not None
                and notion_leaf.ref_id not in filter_ref_ids_set
            ):
                continue

            if notion_leaf.ref_id is None:
                with progress_reporter.start_creating_entity(
                    self._leaf_name, notion_leaf.nice_name
                ) as entity_reporter:
                    new_leaf = notion_leaf.new_entity(trunk.ref_id, inverse_info)

                    with self._storage_engine.get_unit_of_work() as uow:
                        new_leaf = uow.get_leaf_repository_for(self._leaf_type).create(
                            new_leaf
                        )
                        entity_reporter.mark_known_entity_id(
                            new_leaf.ref_id
                        ).mark_local_change()

                    self._notion_manager.link_local_and_notion_leaves(
                        trunk.ref_id, new_leaf.ref_id, notion_leaf.notion_id
                    )
                    entity_reporter.mark_other_progress("linking")

                    notion_leaf = notion_leaf.join_with_entity(new_leaf, direct_info)
                    self._notion_manager.save_leaf(trunk.ref_id, notion_leaf)
                    entity_reporter.mark_remote_change()

                    all_leaves_set[new_leaf.ref_id] = new_leaf
                    all_notion_leaves_set[new_leaf.ref_id] = notion_leaf
                    created_locally.append(new_leaf)
            elif (
                notion_leaf.ref_id in all_leaves_set
                and notion_leaf.notion_id in all_notion_leaves_notion_ids
            ):
                leaf = all_leaves_set[notion_leaf.ref_id]
                all_notion_leaves_set[notion_leaf.ref_id] = notion_leaf

                # If the leaf exists locally, we sync it with the remote:
                with progress_reporter.start_updating_entity(
                    self._leaf_name, leaf.ref_id, notion_leaf.nice_name
                ) as entity_reporter:
                    if sync_prefer == SyncPrefer.NOTION:
                        if (
                            not sync_even_if_not_modified
                            and notion_leaf.last_edited_time <= leaf.last_modified_time
                        ):
                            entity_reporter.mark_not_needed()
                            continue

                        updated_leaf = notion_leaf.apply_to_entity(leaf, inverse_info)

                        with self._storage_engine.get_unit_of_work() as uow:
                            uow.get_leaf_repository_for(self._leaf_type).save(
                                updated_leaf.entity
                            )
                            entity_reporter.mark_local_change()

                        if updated_leaf.should_modify_on_notion:
                            updated_notion_leaf = notion_leaf.join_with_entity(
                                updated_leaf.entity, direct_info
                            )
                            self._notion_manager.save_leaf(
                                trunk.ref_id, updated_notion_leaf
                            )
                            entity_reporter.mark_remote_change()

                        all_leaves_set[notion_leaf.ref_id] = updated_leaf.entity
                        modified_locally.append(updated_leaf.entity)
                    elif sync_prefer == SyncPrefer.LOCAL:
                        entity_reporter.mark_known_name(notion_leaf.nice_name)

                        if (
                            not sync_even_if_not_modified
                            and leaf.last_modified_time <= notion_leaf.last_edited_time
                        ):
                            entity_reporter.mark_not_needed()
                            continue

                        updated_notion_leaf = notion_leaf.join_with_entity(
                            leaf, direct_info
                        )
                        entity_reporter.mark_known_name(updated_notion_leaf.nice_name)

                        self._notion_manager.save_leaf(
                            trunk.ref_id, updated_notion_leaf
                        )
                        entity_reporter.mark_remote_change()

                        all_notion_leaves_set[notion_leaf.ref_id] = updated_notion_leaf
                        modified_remotely.append(leaf)
                    else:
                        raise Exception(f"Invalid preference {sync_prefer}")
            else:
                # If we're here, one of two cases have happened:
                # 1. This is some random leaf added by someone, where they completed themselves a ref_id. It's a bad
                #    setup, and we remove it.
                # 2. This is a leaf added by the script, but which failed before local data could be saved.
                #    We'll have duplicates in these cases, and they need to be removed.
                with progress_reporter.start_updating_entity(
                    self._leaf_name, notion_leaf.ref_id
                ) as entity_reporter:
                    try:
                        self._notion_manager.remove_leaf(
                            trunk.ref_id, notion_leaf.ref_id
                        )
                        entity_reporter.mark_other_progress("remote remove")
                        removed_remotely.append(notion_leaf.ref_id)
                    except NotionLeafEntityNotFoundError:
                        LOGGER.info(
                            f"Skipped dangling leaf in Notion {notion_leaf.ref_id}"
                        )
                        entity_reporter.mark_other_progress(
                            "remote remove", MarkProgressStatus.FAILED
                        )

        # Explore local and apply to Notion now
        for leaf in all_leaves:
            if leaf.ref_id in all_notion_leaves_set:
                # The leaf already exists on Notion side, so it was handled by the above loop!
                continue
            if leaf.archived:
                continue

            # If the leaf does not exist on Notion side, we create it.
            notion_leaf = cast(
                NotionLeafT,
                self._notion_leaf_type.new_notion_entity(
                    cast(Any, leaf), cast(Any, direct_info)
                ),
            )

            with progress_reporter.start_updating_entity(
                self._leaf_name, leaf.ref_id, notion_leaf.nice_name
            ) as entity_reporter:
                self._notion_manager.upsert_leaf(trunk.ref_id, notion_leaf)
                entity_reporter.mark_other_progress("remote create")
            all_notion_leaves_set[leaf.ref_id] = notion_leaf
            created_remotely.append(leaf)

        return SyncResult(
            all=all_leaves_set.values(),
            created_locally=created_locally,
            modified_locally=modified_locally,
            created_remotely=created_remotely,
            modified_remotely=modified_remotely,
            removed_remotely=removed_remotely,
        )


class TrunkBranchLeafNotionSyncService(
    Generic[
        TrunkT,
        BranchT,
        LeafT,
        NotionParentT,
        NotionTrunkT,
        NotionBranchT,
        NotionLeafT,
        NotionLeafDirectExtraInfoT,
        NotionLeafInverseExtraInfoT,
    ]
):
    """The service class for syncing a trunk branch leaf structure between local and Notion."""

    _trunk_type: Type[TrunkT]
    _branch_type: Type[BranchT]
    _branch_name: Final[str]
    _leaf_type: Type[LeafT]
    _leaf_name: Final[str]
    _notion_branch_type: Type[NotionBranchT]
    _notion_leaf_type: Type[NotionLeafT]
    _storage_engine: Final[DomainStorageEngine]
    _notion_manager: ParentTrunkBranchLeafNotionManager[
        NotionParentT,
        NotionTrunkT,
        NotionBranchT,
        NotionLeafT,
    ]

    def __init__(
        self,
        trunk_type: Type[TrunkT],
        branch_type: Type[BranchT],
        branch_name: str,
        leaf_type: Type[LeafT],
        leaf_name: str,
        notion_branch_type: Type[NotionBranchT],
        notion_leaf_type: Type[NotionLeafT],
        storage_engine: DomainStorageEngine,
        notion_manager: ParentTrunkBranchLeafNotionManager[
            NotionParentT,
            NotionTrunkT,
            NotionBranchT,
            NotionLeafT,
        ],
    ) -> None:
        """Constructor."""
        self._trunk_type = trunk_type
        self._branch_type = branch_type
        self._branch_name = branch_name
        self._leaf_type = leaf_type
        self._leaf_name = leaf_name
        self._notion_branch_type = notion_branch_type
        self._notion_leaf_type = notion_leaf_type
        self._storage_engine = storage_engine
        self._notion_manager = notion_manager

    def sync(
        self,
        progress_reporter: ProgressReporter,
        right_now: Timestamp,
        parent_ref_id: EntityId,
        branch: BranchT,
        direct_info: NotionLeafDirectExtraInfoT,
        inverse_info: NotionLeafInverseExtraInfoT,
        drop_all_notion_side: bool,
        sync_even_if_not_modified: bool,
        filter_ref_ids: Optional[Iterable[EntityId]],
        sync_prefer: SyncPrefer,
    ) -> SyncResult[LeafT]:
        """Synchronize a branch and its entries between Notion and local storage."""
        with self._storage_engine.get_unit_of_work() as uow:
            trunk: TrunkT = uow.get_trunk_repository_for(
                self._trunk_type
            ).load_by_parent(parent_ref_id)

        with progress_reporter.start_complex_entity_work(
            self._branch_name, trunk.ref_id, branch.nice_name
        ) as subprogress_reporter:
            with subprogress_reporter.start_updating_entity(
                self._branch_name, trunk.ref_id
            ) as entity_reporter:
                try:
                    notion_branch = self._notion_manager.load_branch(
                        trunk.ref_id, branch.ref_id
                    )

                    if sync_prefer == SyncPrefer.LOCAL:
                        updated_notion_branch = notion_branch.join_with_entity(branch)
                        entity_reporter.mark_known_name(updated_notion_branch.nice_name)
                        self._notion_manager.save_branch(
                            trunk.ref_id, updated_notion_branch
                        )
                        entity_reporter.mark_remote_change()
                    elif sync_prefer == SyncPrefer.NOTION:
                        entity_reporter.mark_known_name(notion_branch.nice_name)

                        # Not 100% happy with the below! Equality comparison seems tricky.
                        new_branch = notion_branch.apply_to_entity(branch, right_now)

                        if sync_even_if_not_modified or new_branch != branch:
                            with self._storage_engine.get_unit_of_work() as uow:
                                branch = uow.get_branch_repository_for(
                                    self._branch_type
                                ).save(new_branch)
                            entity_reporter.mark_local_change()
                        else:
                            entity_reporter.mark_not_needed()
                    else:
                        raise Exception(f"Invalid preference {sync_prefer}")
                except NotionBranchEntityNotFoundError:
                    notion_branch = cast(
                        NotionBranchT,
                        self._notion_branch_type.new_notion_entity(cast(Any, branch)),
                    )
                    entity_reporter.mark_known_name(updated_notion_branch.nice_name)
                    self._notion_manager.upsert_branch(trunk.ref_id, notion_branch)
                    entity_reporter.mark_other_progress("created remote")

            # Now synchronize the list items here.
            filter_ref_ids_set = frozenset(filter_ref_ids) if filter_ref_ids else None

            with self._storage_engine.get_unit_of_work() as uow:
                all_leaves = uow.get_leaf_repository_for(self._leaf_type).find_all(
                    parent_ref_id=branch.ref_id,
                    allow_archived=True,
                    filter_ref_ids=filter_ref_ids_set,
                )
            all_leaves_set: Dict[EntityId, LeafT] = {
                sli.ref_id: sli for sli in all_leaves
            }

            if not drop_all_notion_side:
                all_notion_leaves = self._notion_manager.load_all_leaves(
                    trunk.ref_id, branch.ref_id
                )
                all_notion_branch_notion_ids = set(
                    self._notion_manager.load_all_saved_notion_ids(
                        trunk.ref_id, branch.ref_id
                    )
                )
            else:
                self._notion_manager.drop_all_leaves(trunk.ref_id, branch.ref_id)
                all_notion_leaves = []
                all_notion_branch_notion_ids = set()
            all_notion_leaves_set = {}

            created_locally = []
            modified_locally = []
            created_remotely = []
            modified_remotely = []
            removed_remotely = []

            # Explore Notion and apply to local
            for notion_leaf in all_notion_leaves:
                if (
                    filter_ref_ids_set is not None
                    and notion_leaf.ref_id not in filter_ref_ids_set
                ):
                    continue

                if notion_leaf.ref_id is None:
                    with subprogress_reporter.start_creating_entity(
                        self._leaf_name, notion_leaf.nice_name
                    ) as entity_reporter:
                        # If the branch entry doesn't exist locally, we create it.
                        new_leaf = notion_leaf.new_entity(branch.ref_id, inverse_info)

                        with self._storage_engine.get_unit_of_work() as uow:
                            new_leaf = uow.get_leaf_repository_for(
                                self._leaf_type
                            ).create(new_leaf)
                            entity_reporter.mark_known_entity_id(
                                new_leaf.ref_id
                            ).mark_local_change()

                        self._notion_manager.link_local_and_notion_leaves(
                            trunk.ref_id,
                            branch.ref_id,
                            new_leaf.ref_id,
                            notion_leaf.notion_id,
                        )
                        entity_reporter.mark_other_progress("linking")

                        notion_leaf = notion_leaf.join_with_entity(new_leaf, None)
                        self._notion_manager.save_leaf(
                            trunk.ref_id, branch.ref_id, notion_leaf
                        )
                        entity_reporter.mark_remote_change()

                        all_leaves_set[new_leaf.ref_id] = new_leaf
                        all_notion_leaves_set[new_leaf.ref_id] = notion_leaf
                        created_locally.append(new_leaf)
                elif (
                    notion_leaf.ref_id in all_leaves_set
                    and notion_leaf.notion_id in all_notion_branch_notion_ids
                ):
                    leaf = all_leaves_set[notion_leaf.ref_id]
                    all_notion_leaves_set[notion_leaf.ref_id] = notion_leaf

                    with subprogress_reporter.start_updating_entity(
                        self._leaf_name, leaf.ref_id, notion_leaf.nice_name
                    ) as entity_reporter:
                        if sync_prefer == SyncPrefer.NOTION:
                            if (
                                not sync_even_if_not_modified
                                and notion_leaf.last_edited_time
                                <= leaf.last_modified_time
                            ):
                                entity_reporter.mark_not_needed()
                                continue

                            updated_leaf = notion_leaf.apply_to_entity(
                                leaf, inverse_info
                            )

                            with self._storage_engine.get_unit_of_work() as uow:
                                uow.get_leaf_repository_for(self._leaf_type).save(
                                    updated_leaf.entity
                                )
                                entity_reporter.mark_local_change()

                            if updated_leaf.should_modify_on_notion:
                                updated_notion_leaf = notion_leaf.join_with_entity(
                                    updated_leaf, direct_info
                                )
                                self._notion_manager.save_leaf(
                                    trunk.ref_id, branch.ref_id, updated_notion_leaf
                                )
                                entity_reporter.mark_remote_change()

                            all_leaves_set[notion_leaf.ref_id] = updated_leaf.entity
                            modified_locally.append(updated_leaf.entity)
                        elif sync_prefer == SyncPrefer.LOCAL:
                            if (
                                not sync_even_if_not_modified
                                and leaf.last_modified_time
                                <= notion_leaf.last_edited_time
                            ):
                                entity_reporter.mark_not_needed()
                                continue

                            updated_notion_leaf = notion_leaf.join_with_entity(
                                leaf, direct_info
                            )
                            entity_reporter.mark_known_name(
                                updated_notion_leaf.nice_name
                            )

                            self._notion_manager.save_leaf(
                                trunk.ref_id, branch.ref_id, updated_notion_leaf
                            )
                            entity_reporter.mark_remote_change()

                            all_notion_leaves_set[
                                notion_leaf.ref_id
                            ] = updated_notion_leaf
                            modified_remotely.append(leaf)
                        else:
                            raise Exception(f"Invalid preference {sync_prefer}")
                else:
                    # If we're here, one of two cases have happened:
                    # 1. This is some random branch entry added by someone, where they completed themselves a ref_id.
                    #    It's a bad setup, and we remove it.
                    # 2. This is a branch entry added by the script, but which failed before local data could be saved.
                    #    We'll have duplicates in these cases, and they need to be removed.
                    with subprogress_reporter.start_updating_entity(
                        self._leaf_name, notion_leaf.ref_id
                    ) as entity_reporter:
                        try:
                            self._notion_manager.remove_leaf(
                                trunk.ref_id, branch.ref_id, notion_leaf.ref_id
                            )
                            entity_reporter.mark_other_progress("remote remove")
                            removed_remotely.append(notion_leaf.ref_id)
                        except NotionLeafEntityNotFoundError:
                            LOGGER.info(
                                f"Skipped dangling leaf in Notion {notion_leaf.ref_id}"
                            )
                            entity_reporter.mark_other_progress(
                                "remote remove", MarkProgressStatus.FAILED
                            )

            for leaf in all_leaves:
                if leaf.ref_id in all_notion_leaves_set:
                    # The branch entry already exists on Notion side, so it was handled by the above loop!
                    continue
                if leaf.archived:
                    continue

                # If the branch entry does not exist on Notion side, we create it.
                notion_leaf = cast(
                    NotionLeafT,
                    self._notion_leaf_type.new_notion_entity(
                        cast(Any, leaf), cast(Any, direct_info)
                    ),
                )

                with subprogress_reporter.start_updating_entity(
                    self._leaf_name, leaf.ref_id, notion_leaf.nice_name
                ) as entity_reporter:
                    self._notion_manager.upsert_leaf(
                        trunk.ref_id,
                        branch.ref_id,
                        notion_leaf,
                    )
                    entity_reporter.mark_other_progress("remote create")
                all_notion_leaves_set[leaf.ref_id] = notion_leaf
                created_remotely.append(leaf)

        return SyncResult(
            all=all_leaves_set.values(),
            created_locally=created_locally,
            modified_locally=modified_locally,
            created_remotely=created_remotely,
            modified_remotely=modified_remotely,
            removed_remotely=removed_remotely,
        )


@dataclass(frozen=True)
class _NotionBranchLeafAndTagDirectInfo(Generic[BranchTagT]):
    """Extra info for the app to Notion copy."""

    tags_by_ref_id: Dict[EntityId, BranchTagT]


@dataclass(frozen=True)
class _NotionBranchLeafAndTagInverseInfo(Generic[BranchTagT]):
    """Extra info for the Notion to app copy."""

    tags_by_name: Dict[TagName, BranchTagT]


class TrunkBranchLeafAndTagNotionSyncService(
    Generic[
        TrunkT,
        BranchT,
        LeafT,
        BranchTagT,
        NotionParentT,
        NotionTrunkT,
        NotionBranchT,
        NotionLeafT,
        NotionBranchTagT,
    ]
):
    """The service class for syncing a trunk branch leaf structure between local and Notion."""

    _trunk_type: Type[TrunkT]
    _branch_type: Type[BranchT]
    _branch_name: Final[str]
    _leaf_type: Type[LeafT]
    _leaf_name: Final[str]
    _branch_tag_type: Type[BranchTagT]
    _branch_tag_name: Final[str]
    _notion_branch_type: Type[NotionBranchT]
    _notion_leaf_type: Type[NotionLeafT]
    _notion_branch_tag_type: Type[NotionBranchTagT]
    _storage_engine: Final[DomainStorageEngine]
    _notion_manager: ParentTrunkBranchLeafAndTagNotionManager[
        NotionParentT,
        NotionTrunkT,
        NotionBranchT,
        NotionLeafT,
        NotionBranchTagT,
    ]

    def __init__(
        self,
        trunk_type: Type[TrunkT],
        branch_type: Type[BranchT],
        branch_name: str,
        leaf_type: Type[LeafT],
        leaf_name: str,
        branch_tag_type: Type[BranchTagT],
        branch_tag_name: str,
        notion_branch_type: Type[NotionBranchT],
        notion_leaf_type: Type[NotionLeafT],
        notion_branch_tag_type: Type[NotionBranchTagT],
        storage_engine: DomainStorageEngine,
        notion_manager: ParentTrunkBranchLeafAndTagNotionManager[
            NotionParentT,
            NotionTrunkT,
            NotionBranchT,
            NotionLeafT,
            NotionBranchTagT,
        ],
    ) -> None:
        """Constructor."""
        self._trunk_type = trunk_type
        self._branch_type = branch_type
        self._branch_name = branch_name
        self._leaf_type = leaf_type
        self._leaf_name = leaf_name
        self._branch_tag_type = branch_tag_type
        self._branch_tag_name = branch_tag_name
        self._notion_branch_type = notion_branch_type
        self._notion_leaf_type = notion_leaf_type
        self._notion_branch_tag_type = notion_branch_tag_type
        self._storage_engine = storage_engine
        self._notion_manager = notion_manager

    def sync(
        self,
        progress_reporter: ProgressReporter,
        right_now: Timestamp,
        parent_ref_id: EntityId,
        branch: BranchT,
        drop_all_notion_side: bool,
        sync_even_if_not_modified: bool,
        filter_ref_ids: Optional[Iterable[EntityId]],
        sync_prefer: SyncPrefer,
    ) -> SyncResult[LeafT]:
        """Synchronize a branch and its entries between Notion and local storage."""
        with self._storage_engine.get_unit_of_work() as uow:
            trunk: TrunkT = uow.get_trunk_repository_for(
                self._trunk_type
            ).load_by_parent(parent_ref_id)

        with progress_reporter.start_complex_entity_work(
            self._branch_name, trunk.ref_id, branch.nice_name
        ) as subprogress_reporter:
            with subprogress_reporter.start_updating_entity(
                self._branch_name, trunk.ref_id
            ) as entity_reporter:
                try:
                    notion_branch = self._notion_manager.load_branch(
                        trunk.ref_id, branch.ref_id
                    )

                    if sync_prefer == SyncPrefer.LOCAL:
                        updated_notion_branch = notion_branch.join_with_entity(branch)
                        entity_reporter.mark_known_name(updated_notion_branch.nice_name)
                        self._notion_manager.save_branch(
                            trunk.ref_id, updated_notion_branch
                        )
                        entity_reporter.mark_remote_change()
                    elif sync_prefer == SyncPrefer.NOTION:
                        entity_reporter.mark_known_name(notion_branch.nice_name)

                        # Not 100% happy with the below! Equality comparison seems tricky.
                        new_branch = notion_branch.apply_to_entity(branch, right_now)

                        if sync_even_if_not_modified or new_branch != branch:
                            with self._storage_engine.get_unit_of_work() as uow:
                                branch = uow.get_branch_repository_for(
                                    self._branch_type
                                ).save(new_branch)
                            entity_reporter.mark_local_change()
                        else:
                            entity_reporter.mark_not_needed()
                    else:
                        raise Exception(f"Invalid preference {sync_prefer}")
                except NotionBranchEntityNotFoundError:
                    notion_branch = cast(
                        NotionBranchT,
                        self._notion_branch_type.new_notion_entity(cast(Any, branch)),
                    )
                    entity_reporter.mark_known_name(updated_notion_branch.nice_name)
                    self._notion_manager.upsert_branch(trunk.ref_id, notion_branch)
                    entity_reporter.mark_other_progress("created remote")

            # Sync the tags
            with self._storage_engine.get_unit_of_work() as uow:
                all_branch_tags = uow.get_leaf_repository_for(
                    self._branch_tag_type
                ).find_all(parent_ref_id=branch.ref_id, allow_archived=True)
            all_branch_tags_set = {slt.ref_id: slt for slt in all_branch_tags}
            all_branch_tags_by_name = {slt.tag_name: slt for slt in all_branch_tags}

            if not drop_all_notion_side:
                all_notion_branch_tags = self._notion_manager.load_all_branch_tags(
                    trunk.ref_id, branch.ref_id
                )
                all_notion_branch_tags_notion_ids = set(
                    self._notion_manager.load_all_saved_branch_tags_notion_ids(
                        trunk.ref_id, branch.ref_id
                    )
                )
            else:
                self._notion_manager.drop_all_branch_tags(trunk.ref_id, branch.ref_id)
                all_notion_branch_tags = []
                all_notion_branch_tags_notion_ids = set()
            notion_branch_tags_set = {}

            for notion_branch_tag in all_notion_branch_tags:
                if notion_branch_tag.ref_id is None:
                    with subprogress_reporter.start_creating_entity(
                        self._branch_tag_name, notion_branch_tag.nice_name
                    ) as entity_reporter:
                        # If the branch tag doesn't exist locally, we create it.
                        new_branch_tag = notion_branch_tag.new_entity(branch.ref_id)
                        with self._storage_engine.get_unit_of_work() as uow:
                            new_branch_tag = uow.get_leaf_repository_for(
                                self._branch_tag_type
                            ).create(new_branch_tag)
                            entity_reporter.mark_known_entity_id(
                                new_branch_tag.ref_id
                            ).mark_local_change()

                        self._notion_manager.link_local_and_notion_branch_tags(
                            trunk.ref_id,
                            branch.ref_id,
                            new_branch_tag.ref_id,
                            notion_branch_tag.notion_id,
                        )
                        entity_reporter.mark_other_progress("linking")

                        notion_branch_tag = notion_branch_tag.join_with_entity(
                            new_branch_tag
                        )
                        self._notion_manager.save_branch_tag(
                            trunk.ref_id, branch.ref_id, notion_branch_tag
                        )
                        entity_reporter.mark_remote_change()

                        notion_branch_tags_set[
                            new_branch_tag.ref_id
                        ] = notion_branch_tag
                        all_branch_tags.append(new_branch_tag)
                        all_branch_tags_set[new_branch_tag.ref_id] = new_branch_tag
                        all_branch_tags_by_name[
                            new_branch_tag.tag_name
                        ] = new_branch_tag
                elif (
                    notion_branch_tag.ref_id in all_branch_tags_set
                    and notion_branch_tag.notion_id in all_notion_branch_tags_notion_ids
                ):
                    branch_tag = all_branch_tags_set[notion_branch_tag.ref_id]
                    notion_branch_tags_set[notion_branch_tag.ref_id] = notion_branch_tag

                    with subprogress_reporter.start_updating_entity(
                        self._branch_tag_name,
                        branch_tag.ref_id,
                        notion_branch_tag.nice_name,
                    ) as entity_reporter:
                        if sync_prefer == SyncPrefer.NOTION:
                            updated_branch_tag = notion_branch_tag.apply_to_entity(
                                branch_tag
                            )

                            if (
                                branch_tag.tag_name
                                == updated_branch_tag.entity.tag_name
                            ):
                                entity_reporter.mark_not_needed()
                                continue

                            with self._storage_engine.get_unit_of_work() as uow:
                                uow.get_leaf_repository_for(self._branch_tag_type).save(
                                    updated_branch_tag.entity
                                )
                                entity_reporter.mark_local_change()

                            all_branch_tags_set[
                                notion_branch_tag.ref_id
                            ] = updated_branch_tag.entity
                            all_branch_tags_by_name[
                                branch_tag.tag_name
                            ] = updated_branch_tag.entity
                        elif sync_prefer == SyncPrefer.LOCAL:
                            updated_notion_branch_tag = (
                                notion_branch_tag.join_with_entity(branch_tag)
                            )
                            entity_reporter.mark_known_name(str(branch_tag.tag_name))
                            self._notion_manager.save_branch_tag(
                                trunk.ref_id, branch.ref_id, updated_notion_branch_tag
                            )
                            entity_reporter.mark_remote_change()
                        else:
                            raise Exception(f"Invalid preference {sync_prefer}")
                else:
                    # If we're here, one of two cases have happened:
                    # 1. This is some random branch tag added by someone, where they completed themselves a ref_id.
                    #    It's a bad setup, and we remove it.
                    # 2. This is a smart list item added by the script, but which failed before local data could be saved.
                    #    We'll have duplicates in these cases, and they need to be removed.
                    with subprogress_reporter.start_updating_entity(
                        self._branch_tag_name, notion_branch_tag.ref_id
                    ) as entity_reporter:
                        try:
                            self._notion_manager.remove_branch_tag(
                                trunk.ref_id, branch.ref_id, notion_branch_tag.ref_id
                            )
                            entity_reporter.mark_other_progress("remote remove")
                        except NotionLeafEntityNotFoundError:
                            LOGGER.info(
                                f"Skipped dangling branch tag in Notion {notion_branch_tag.ref_id}"
                            )
                            entity_reporter.mark_other_progress(
                                "remote remove", MarkProgressStatus.FAILED
                            )

            for branch_tag in all_branch_tags:
                if branch_tag.ref_id in notion_branch_tags_set:
                    # The smart list item already exists on Notion side, so it was handled by the above loop!
                    continue
                if branch_tag.archived:
                    continue

                # If the smart list item does not exist on Notion side, we create it.
                notion_branch_tag = cast(
                    NotionBranchTagT,
                    self._notion_branch_tag_type.new_notion_entity(
                        cast(Any, branch_tag)
                    ),
                )

                with subprogress_reporter.start_updating_entity(
                    self._branch_tag_name, branch_tag.ref_id, str(branch_tag.tag_name)
                ) as entity_reporter:
                    self._notion_manager.upsert_branch_tag(
                        trunk.ref_id, branch.ref_id, notion_branch_tag
                    )
                    entity_reporter.mark_other_progress("remote create")

            # Now synchronize the list items here.
            filter_ref_ids_set = frozenset(filter_ref_ids) if filter_ref_ids else None

            with self._storage_engine.get_unit_of_work() as uow:
                all_leaves = uow.get_leaf_repository_for(self._leaf_type).find_all(
                    parent_ref_id=branch.ref_id,
                    allow_archived=True,
                    filter_ref_ids=filter_ref_ids_set,
                )
            all_leaves_set: Dict[EntityId, LeafT] = {
                sli.ref_id: sli for sli in all_leaves
            }

            if not drop_all_notion_side:
                all_notion_leaves = self._notion_manager.load_all_leaves(
                    trunk.ref_id, branch.ref_id
                )
                all_notion_branch_notion_ids = set(
                    self._notion_manager.load_all_saved_notion_ids(
                        trunk.ref_id, branch.ref_id
                    )
                )
            else:
                self._notion_manager.drop_all_leaves(trunk.ref_id, branch.ref_id)
                all_notion_leaves = []
                all_notion_branch_notion_ids = set()
            all_notion_leaves_set = {}

            direct_info = _NotionBranchLeafAndTagDirectInfo(
                tags_by_ref_id=all_branch_tags_set
            )
            inverse_info = _NotionBranchLeafAndTagInverseInfo(
                tags_by_name=all_branch_tags_by_name
            )

            created_locally = []
            modified_locally = []
            created_remotely = []
            modified_remotely = []
            removed_remotely = []

            # Explore Notion and apply to local
            for notion_leaf in all_notion_leaves:
                if (
                    filter_ref_ids_set is not None
                    and notion_leaf.ref_id not in filter_ref_ids_set
                ):
                    continue

                if notion_leaf.ref_id is None:
                    with subprogress_reporter.start_creating_entity(
                        self._leaf_name, notion_leaf.nice_name
                    ) as entity_reporter:
                        # If the branch entry doesn't exist locally, we create it.
                        new_leaf = notion_leaf.new_entity(branch.ref_id, inverse_info)

                        with self._storage_engine.get_unit_of_work() as uow:
                            new_leaf = uow.get_leaf_repository_for(
                                self._leaf_type
                            ).create(new_leaf)
                            entity_reporter.mark_known_entity_id(
                                new_leaf.ref_id
                            ).mark_local_change()

                        self._notion_manager.link_local_and_notion_leaves(
                            trunk.ref_id,
                            branch.ref_id,
                            new_leaf.ref_id,
                            notion_leaf.notion_id,
                        )
                        entity_reporter.mark_other_progress("linking")

                        notion_leaf = notion_leaf.join_with_entity(
                            new_leaf, direct_info
                        )
                        self._notion_manager.save_leaf(
                            trunk.ref_id, branch.ref_id, notion_leaf
                        )
                        entity_reporter.mark_remote_change()

                        all_leaves_set[new_leaf.ref_id] = new_leaf
                        all_notion_leaves_set[new_leaf.ref_id] = notion_leaf
                        created_locally.append(new_leaf)
                elif (
                    notion_leaf.ref_id in all_leaves_set
                    and notion_leaf.notion_id in all_notion_branch_notion_ids
                ):
                    leaf = all_leaves_set[notion_leaf.ref_id]
                    all_notion_leaves_set[notion_leaf.ref_id] = notion_leaf

                    with subprogress_reporter.start_updating_entity(
                        self._leaf_name, leaf.ref_id, notion_leaf.nice_name
                    ) as entity_reporter:
                        if sync_prefer == SyncPrefer.NOTION:
                            if (
                                not sync_even_if_not_modified
                                and notion_leaf.last_edited_time
                                <= leaf.last_modified_time
                            ):
                                entity_reporter.mark_not_needed()
                                continue

                            updated_leaf = notion_leaf.apply_to_entity(
                                leaf, inverse_info
                            )

                            with self._storage_engine.get_unit_of_work() as uow:
                                uow.get_leaf_repository_for(self._leaf_type).save(
                                    updated_leaf.entity
                                )
                                entity_reporter.mark_local_change()

                            if updated_leaf.should_modify_on_notion:
                                updated_notion_leaf = notion_leaf.join_with_entity(
                                    updated_leaf, direct_info
                                )
                                self._notion_manager.save_leaf(
                                    trunk.ref_id, branch.ref_id, updated_notion_leaf
                                )
                                entity_reporter.mark_remote_change()

                            all_leaves_set[notion_leaf.ref_id] = updated_leaf.entity
                            modified_locally.append(updated_leaf.entity)
                        elif sync_prefer == SyncPrefer.LOCAL:
                            if (
                                not sync_even_if_not_modified
                                and leaf.last_modified_time
                                <= notion_leaf.last_edited_time
                            ):
                                entity_reporter.mark_not_needed()
                                continue

                            updated_notion_leaf = notion_leaf.join_with_entity(
                                leaf, direct_info
                            )
                            entity_reporter.mark_known_name(
                                updated_notion_leaf.nice_name
                            )

                            self._notion_manager.save_leaf(
                                trunk.ref_id, branch.ref_id, updated_notion_leaf
                            )
                            entity_reporter.mark_remote_change()

                            all_notion_leaves_set[
                                notion_leaf.ref_id
                            ] = updated_notion_leaf
                            modified_remotely.append(leaf)
                        else:
                            raise Exception(f"Invalid preference {sync_prefer}")
                else:
                    # If we're here, one of two cases have happened:
                    # 1. This is some random branch entry added by someone, where they completed themselves a ref_id.
                    #    It's a bad setup, and we remove it.
                    # 2. This is a branch entry added by the script, but which failed before local data could be saved.
                    #    We'll have duplicates in these cases, and they need to be removed.
                    with subprogress_reporter.start_updating_entity(
                        self._leaf_name, notion_leaf.ref_id
                    ) as entity_reporter:
                        try:
                            self._notion_manager.remove_leaf(
                                trunk.ref_id, branch.ref_id, notion_leaf.ref_id
                            )
                            entity_reporter.mark_other_progress("remote remove")
                            removed_remotely.append(notion_leaf.ref_id)
                        except NotionLeafEntityNotFoundError:
                            LOGGER.info(
                                f"Skipped dangling leaf in Notion {notion_leaf.ref_id}"
                            )
                            entity_reporter.mark_other_progress(
                                "remote remove", MarkProgressStatus.FAILED
                            )

            for leaf in all_leaves:
                if leaf.ref_id in all_notion_leaves_set:
                    # The branch entry already exists on Notion side, so it was handled by the above loop!
                    continue
                if leaf.archived:
                    continue

                # If the branch entry does not exist on Notion side, we create it.
                notion_leaf = cast(
                    NotionLeafT,
                    self._notion_leaf_type.new_notion_entity(
                        cast(Any, leaf), cast(Any, direct_info)
                    ),
                )

                with subprogress_reporter.start_updating_entity(
                    self._leaf_name, leaf.ref_id, notion_leaf.nice_name
                ) as entity_reporter:
                    self._notion_manager.upsert_leaf(
                        trunk.ref_id,
                        branch.ref_id,
                        notion_leaf,
                    )
                    entity_reporter.mark_other_progress("remote create")
                all_notion_leaves_set[leaf.ref_id] = notion_leaf
                created_remotely.append(leaf)

        return SyncResult(
            all=all_leaves_set.values(),
            created_locally=created_locally,
            modified_locally=modified_locally,
            created_remotely=created_remotely,
            modified_remotely=modified_remotely,
            removed_remotely=removed_remotely,
        )
