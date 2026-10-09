"""Email provider abstraction package."""
from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.provider.outlook_provider import OutlookComProvider
from py_inbox_helper.provider.imap_provider import ImapMailProvider, ImapConfig, ImapProfileManager

__all__ = [
    "AccountInfo",
    "FolderInfo",
    "BaseMailProvider",
    "MockMailProvider",
    "OutlookComProvider",
    "ImapMailProvider",
    "ImapConfig",
    "ImapProfileManager",
]
