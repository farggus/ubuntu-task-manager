"""Base collector class for all data collectors."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseCollector(ABC):
    """Base class for all collectors."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize collector.

        Args:
            config: Configuration dictionary for this collector
        """
        self.config = config or {}
        self.last_update: Optional[datetime] = None
        self.data: Dict[str, Any] = {}
        self.errors: list = []

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        Collect data from the system.

        Returns:
            Dictionary with collected data
        """
        pass

    def update(self) -> Dict[str, Any]:
        """
        Update collected data and timestamp.

        Returns:
            Updated data dictionary
        """
        try:
            self.data = self.collect()
            self.last_update = datetime.now()
            self.errors = []
        except Exception as e:
            error_msg = f"Error collecting data: {str(e)}"
            logger.error(f"{self.name}: {error_msg}", exc_info=True)
            self.errors.append(error_msg)
            self.data['error'] = error_msg

        return self.data

    def get_data(self) -> Dict[str, Any]:
        """
        Get current data without updating.

        Returns:
            Current data dictionary
        """
        return self.data

    def has_errors(self) -> bool:
        """Check if collector has errors."""
        return len(self.errors) > 0

    @property
    def name(self) -> str:
        """Get collector name."""
        return self.__class__.__name__.replace('Collector', '')
