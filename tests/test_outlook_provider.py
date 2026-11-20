"""Tests for OutlookComProvider mailbox resolution, using fake COM objects."""
from unittest.mock import MagicMock
import pytest

pytest.importorskip("win32com.client")

from py_inbox_helper.models import PlannedAction
from py_inbox_helper.provider.outlook_provider import OL_FOLDER_DELETED_ITEMS, OutlookComProvider


class FakeFolders:
    def __init__(self, owner):
        self._owner = owner
        self._items = []

    @property
    def Count(self):
        return len(self._items)

    def Item(self, index):
        return self._items[index - 1]

    def Add(self, name):
        folder = FakeFolder(name, self._owner.Store)
        self._items.append(folder)
        return folder


class FakeFolder:
    def __init__(self, name, store):
        self.Name = name
        self.Store = store
        self.StoreID = store.StoreID
        self.EntryID = f"{store.StoreID}-{name}"
        self.Folders = FakeFolders(self)


class FakeStore:
    def __init__(self, store_id, name):
        self.StoreID = store_id
        self.root = FakeFolder(name, self)
        self.deleted_items = self.root.Folders.Add("Gelöschte Elemente")
        self.root.Folders.Add("Posteingang")

    def GetDefaultFolder(self, folder_type):
        assert folder_type == OL_FOLDER_DELETED_ITEMS
        return self.deleted_items

    def GetRootFolder(self):
        return self.root


@pytest.fixture
def outlook():
    """Provider wired to two mailboxes: the default one and a shared one."""
    primary = FakeStore("STORE-PRIMARY", "ich@firma.de")
    shared = FakeStore("STORE-SHARED", "support@firma.de")

    namespace = MagicMock()
    namespace.Folders.Count = 2
    namespace.Folders.Item.side_effect = lambda i: [primary.root, shared.root][i - 1]
    namespace.GetStoreFromID.side_effect = LookupError("unknown store")
    # Outlook's own default folder always belongs to the primary mailbox
    namespace.GetDefaultFolder.return_value = primary.deleted_items

    provider = OutlookComProvider()
    provider._app = MagicMock()
    provider._namespace = namespace
    return provider, namespace, primary, shared


def test_trash_goes_to_deleted_items_of_selected_mailbox(outlook):
    provider, namespace, primary, shared = outlook
    item = MagicMock()
    item.Move.return_value = item
    namespace.GetItemFromID.return_value = item

    action = PlannedAction(email_id="ENTRY1_1", email_subject="Spam", target_folder="Gelöschte Elemente")
    result = provider.execute_action(action, "STORE-SHARED")

    assert result.success, result.message
    item.Move.assert_called_once_with(shared.deleted_items)


def test_target_folder_is_created_in_selected_mailbox(outlook):
    provider, namespace, primary, shared = outlook
    item = MagicMock()
    item.Move.return_value = item
    namespace.GetItemFromID.return_value = item

    action = PlannedAction(email_id="ENTRY1_1", email_subject="News", target_folder="04_Newsletter")
    result = provider.execute_action(action, "STORE-SHARED")

    assert result.success, result.message
    shared_names = [shared.root.Folders.Item(i).Name for i in range(1, shared.root.Folders.Count + 1)]
    primary_names = [primary.root.Folders.Item(i).Name for i in range(1, primary.root.Folders.Count + 1)]
    assert "04_Newsletter" in shared_names
    assert "04_Newsletter" not in primary_names


def test_unknown_mailbox_never_falls_back_to_first_mailbox(outlook):
    provider, namespace, primary, shared = outlook

    with pytest.raises(LookupError, match="nicht gefunden"):
        provider.list_folders("STORE-GONE")
    with pytest.raises(LookupError, match="nicht gefunden"):
        provider.fetch_emails("STORE-GONE", ["Posteingang"])

    item = MagicMock()
    namespace.GetItemFromID.return_value = item
    action = PlannedAction(email_id="ENTRY1_1", email_subject="News", target_folder="04_Newsletter")
    result = provider.execute_action(action, "STORE-GONE")

    assert result.success is False
    assert "nicht gefunden" in result.message
    item.Move.assert_not_called()
    assert primary.root.Folders.Count == 2  # nothing created in the first mailbox
