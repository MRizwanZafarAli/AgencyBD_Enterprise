"""
Base Autonomous Agent Abstraction for AgencyBD Enterprise.
Provides standard lifecycle hook subscriptions, skill invocation, state management, and telemetry.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from core.logger import get_enterprise_logger
from core.hooks import event_bus
from core.skills import skill_registry, BaseSkill

logger = get_enterprise_logger("BaseAgent")


class BaseAgent(ABC):
    """
    Abstract Base Agent representing an autonomous actor in the BD swarm.
    Subscribes to lifecycle hooks, executes modular skills, and communicates via the EventBus.
    """

    name: str = "base_agent"
    role: str = "Autonomous Actor"
    description: str = "Base autonomous agent"
    subscribed_hooks: List[str] = []
    skills: List[str] = []

    def __init__(self, org_id: str = "org_default"):
        self.org_id = org_id
        self.state = "idle"  # idle | running | error
        self.last_action_at: Optional[float] = None
        self.total_actions: int = 0
        self._registered = False

    def register_lifecycle_hooks(self):
        """Registers the agent's event handlers with the global EventBus."""
        if self._registered:
            return
        for hook_name in self.subscribed_hooks:
            event_bus.register(
                hook_name,
                lambda payload, h=hook_name: self.handle_event(h, payload),
                priority=50,
                name=f"{self.name}:{hook_name}",
            )
        self._registered = True
        logger.info(f"Agent [{self.name}] subscribed to hooks: {self.subscribed_hooks}")

    @abstractmethod
    def handle_event(self, event_name: str, payload: Dict[str, Any]):
        """Handler triggered when an event the agent is subscribed to fires."""
        raise NotImplementedError

    def execute_skill(self, skill_name: str, params: Any) -> Any:
        """Executes a registered skill, attributing telemetry to this agent."""
        skill = skill_registry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found in registry")
        
        self.state = "running"
        self.last_action_at = time.time()
        try:
            result = skill.run(params, org_id=self.org_id, agent_name=self.name)
            self.total_actions += 1
            self.state = "idle"
            return result
        except Exception as e:
            self.state = "error"
            logger.error(f"Agent [{self.name}] failed executing skill [{skill_name}]: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "state": self.state,
            "subscribed_hooks": self.subscribed_hooks,
            "skills": self.skills,
            "total_actions": self.total_actions,
            "last_action_at": self.last_action_at,
        }
