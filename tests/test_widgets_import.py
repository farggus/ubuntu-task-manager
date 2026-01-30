"""Tests for widget imports."""

import unittest


class TestWidgetImports(unittest.TestCase):
    """Tests for widget module imports."""

    def test_import_containers(self):
        """Test that containers widget can be imported."""
        from dashboard.widgets.containers import ContainersTab
        self.assertIsNotNone(ContainersTab)

    def test_import_disks(self):
        """Test that disks widget can be imported."""
        from dashboard.widgets.disks import DisksTab
        self.assertIsNotNone(DisksTab)

    def test_import_network(self):
        """Test that network widget can be imported."""
        from dashboard.widgets.network import NetworkExtendedTab
        self.assertIsNotNone(NetworkExtendedTab)

    def test_import_packages(self):
        """Test that packages widget can be imported."""
        from dashboard.widgets.packages import PackagesTab
        self.assertIsNotNone(PackagesTab)

    def test_import_processes(self):
        """Test that processes widget can be imported."""
        from dashboard.widgets.processes import ProcessesTab
        self.assertIsNotNone(ProcessesTab)

    def test_import_services(self):
        """Test that services widget can be imported."""
        from dashboard.widgets.services import ServicesTab
        self.assertIsNotNone(ServicesTab)

    def test_import_tasks(self):
        """Test that tasks widget can be imported."""
        from dashboard.widgets.tasks import TasksExtendedTab
        self.assertIsNotNone(TasksExtendedTab)

    def test_import_users(self):
        """Test that users widget can be imported."""
        from dashboard.widgets.users import UsersTab
        self.assertIsNotNone(UsersTab)

    def test_import_logging(self):
        """Test that logging widget can be imported."""
        from dashboard.widgets.logging import LoggingTab
        self.assertIsNotNone(LoggingTab)

    def test_import_smart_modal(self):
        """Test that smart modal can be imported."""
        from dashboard.widgets.smart_modal import SmartModal
        self.assertIsNotNone(SmartModal)

    def test_import_mount_modal(self):
        """Test that mount modal can be imported."""
        from dashboard.widgets.mount_modal import MountModal
        self.assertIsNotNone(MountModal)

    def test_import_fstab_modal(self):
        """Test that fstab modal can be imported."""
        from dashboard.widgets.fstab_modal import FstabModal
        self.assertIsNotNone(FstabModal)

    def test_import_disk_details_modal(self):
        """Test that disk details modal can be imported."""
        from dashboard.widgets.disk_details_modal import DiskDetailsModal
        self.assertIsNotNone(DiskDetailsModal)

    def test_import_container_log_modal(self):
        """Test that container log modal can be imported."""
        from dashboard.widgets.container_log_modal import ContainerLogModal
        self.assertIsNotNone(ContainerLogModal)


class TestWidgetInheritance(unittest.TestCase):
    """Tests for widget inheritance."""

    def test_tabs_are_textual_widgets(self):
        """Test that tab widgets are Textual widget subclasses."""
        from textual.containers import Vertical

        from dashboard.widgets.containers import ContainersTab
        from dashboard.widgets.processes import ProcessesTab
        from dashboard.widgets.services import ServicesTab

        self.assertTrue(issubclass(ContainersTab, Vertical))
        self.assertTrue(issubclass(ProcessesTab, Vertical))
        self.assertTrue(issubclass(ServicesTab, Vertical))

    def test_modals_are_modal_screens(self):
        """Test that modals are ModalScreen subclasses."""
        from textual.screen import ModalScreen

        from dashboard.widgets.smart_modal import SmartModal
        from dashboard.widgets.mount_modal import MountModal

        self.assertTrue(issubclass(SmartModal, ModalScreen))
        self.assertTrue(issubclass(MountModal, ModalScreen))


class TestFail2banWidgets(unittest.TestCase):
    """Tests for Fail2ban widgets."""

    def test_import_fail2ban_tab(self):
        """Test that fail2ban tab can be imported."""
        from dashboard.widgets.fail2ban import Fail2banTab
        self.assertIsNotNone(Fail2banTab)

    def test_import_fail2ban_plus_tab(self):
        """Test that fail2ban plus tab can be imported."""
        from dashboard.widgets.fail2ban_plus import Fail2banPlusTab
        self.assertIsNotNone(Fail2banPlusTab)

    def test_import_whitelist_modal(self):
        """Test that whitelist modal can be imported."""
        from dashboard.widgets.whitelist_modal import WhitelistModal
        self.assertIsNotNone(WhitelistModal)

    def test_import_confirm_modal(self):
        """Test that confirm modal can be imported."""
        from dashboard.widgets.confirm_modal import ConfirmModal
        self.assertIsNotNone(ConfirmModal)

    def test_import_analysis_modal(self):
        """Test that analysis modal can be imported."""
        from dashboard.widgets.analysis_modal import AnalysisModal
        self.assertIsNotNone(AnalysisModal)


class TestSystemInfoWidget(unittest.TestCase):
    """Tests for system info widget."""

    def test_import_compact_system_info(self):
        """Test that CompactSystemInfo can be imported."""
        from dashboard.widgets.system_info import CompactSystemInfo
        self.assertIsNotNone(CompactSystemInfo)


class TestWidgetCSS(unittest.TestCase):
    """Tests for widget CSS definitions."""

    def test_fail2ban_tab_has_css(self):
        """Test Fail2banTab has CSS defined."""
        from dashboard.widgets.fail2ban import Fail2banTab
        # Check if CSS class attribute exists
        self.assertTrue(hasattr(Fail2banTab, 'DEFAULT_CSS') or hasattr(Fail2banTab, 'CSS'))

    def test_disks_tab_has_css(self):
        """Test DisksTab has CSS defined."""
        from dashboard.widgets.disks import DisksTab
        self.assertTrue(hasattr(DisksTab, 'DEFAULT_CSS') or hasattr(DisksTab, 'CSS'))


class TestWidgetBindings(unittest.TestCase):
    """Tests for widget key bindings."""

    def test_fail2ban_has_bindings(self):
        """Test Fail2banTab has key bindings."""
        from dashboard.widgets.fail2ban import Fail2banTab
        self.assertTrue(hasattr(Fail2banTab, 'BINDINGS'))

    def test_processes_has_bindings(self):
        """Test ProcessesTab has key bindings."""
        from dashboard.widgets.processes import ProcessesTab
        self.assertTrue(hasattr(ProcessesTab, 'BINDINGS'))

    def test_containers_has_bindings(self):
        """Test ContainersTab has key bindings."""
        from dashboard.widgets.containers import ContainersTab
        self.assertTrue(hasattr(ContainersTab, 'BINDINGS'))

    def test_services_has_bindings(self):
        """Test ServicesTab has key bindings."""
        from dashboard.widgets.services import ServicesTab
        self.assertTrue(hasattr(ServicesTab, 'BINDINGS'))

    def test_logging_has_bindings(self):
        """Test LoggingTab has key bindings."""
        from dashboard.widgets.logging import LoggingTab
        self.assertTrue(hasattr(LoggingTab, 'BINDINGS'))

    def test_users_has_bindings(self):
        """Test UsersTab has key bindings."""
        from dashboard.widgets.users import UsersTab
        self.assertTrue(hasattr(UsersTab, 'BINDINGS'))


class TestF2bDbManageModal(unittest.TestCase):
    """Tests for F2B database manage modal."""

    def test_import_f2b_db_manage_modal(self):
        """Test that F2BDatabaseModal can be imported."""
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal
        self.assertIsNotNone(F2BDatabaseModal)

    def test_f2b_db_manage_modal_is_modal(self):
        """Test that F2BDatabaseModal is a ModalScreen."""
        from textual.screen import ModalScreen
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal
        self.assertTrue(issubclass(F2BDatabaseModal, ModalScreen))


if __name__ == '__main__':
    unittest.main()
