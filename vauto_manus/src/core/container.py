"""
Dependency injection container for the vAuto Feature Verification System.

This module provides a container for managing dependencies and implementing
dependency injection throughout the application.
"""

import logging
from typing import Any, Dict, Optional, Type, TypeVar, cast

from .interfaces import (
    BrowserInterface,
    AuthenticationInterface,
    InventoryDiscoveryInterface,
    WindowStickerInterface,
    FeatureMapperInterface,
    CheckboxManagementInterface,
    ReportingInterface,
    WorkflowInterface,
    ConfigurationInterface
)
from .config import ConfigurationManager
from .browser import SeleniumBrowser

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Container:
    """Dependency injection container."""
    
    def __init__(self):
        """Initialize the container."""
        self._instances: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        
        logger.info("Dependency injection container initialized")
    
    def register(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register an implementation for an interface.
        
        Args:
            interface: Interface type
            implementation: Implementation type
        """
        logger.debug(f"Registering implementation for {interface.__name__}")
        self._factories[interface] = implementation
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """
        Register an instance for an interface.
        
        Args:
            interface: Interface type
            instance: Implementation instance
        """
        logger.debug(f"Registering instance for {interface.__name__}")
        self._instances[interface] = instance
    
    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve an implementation for an interface.
        
        Args:
            interface: Interface type
            
        Returns:
            Implementation instance
            
        Raises:
            ValueError: If no implementation is registered for the interface
        """
        # Check if we already have an instance
        if interface in self._instances:
            return cast(T, self._instances[interface])
        
        # Check if we have a factory
        if interface in self._factories:
            implementation = self._factories[interface]
            instance = implementation()
            self._instances[interface] = instance
            return cast(T, instance)
        
        raise ValueError(f"No implementation registered for {interface.__name__}")


def create_container(config_dir: str = "configs") -> Container:
    """
    Create and configure a dependency injection container.
    
    Args:
        config_dir: Directory containing configuration files
        
    Returns:
        Container: Configured container
    """
    container = Container()
    
    # Create and register configuration manager
    config_manager = ConfigurationManager(config_dir)
    container.register_instance(ConfigurationInterface, config_manager)
    
    # Get system configuration
    system_config = config_manager.get_system_config()
    
    # Register browser
    browser = SeleniumBrowser(system_config["browser"])
    container.register_instance(BrowserInterface, browser)
    
    # Register other components (these will be implemented later)
    # container.register(AuthenticationInterface, AuthenticationModule)
    # container.register(InventoryDiscoveryInterface, InventoryDiscoveryModule)
    # container.register(WindowStickerInterface, WindowStickerProcessor)
    # container.register(FeatureMapperInterface, FeatureMapper)
    # container.register(CheckboxManagementInterface, CheckboxManagementModule)
    # container.register(ReportingInterface, ReportingModule)
    # container.register(WorkflowInterface, VerificationWorkflow)
    
    logger.info("Dependency injection container configured")
    return container
