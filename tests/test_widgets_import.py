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


if __name__ == '__main__':
    unittest.main()
